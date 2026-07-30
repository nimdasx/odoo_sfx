import requests
import urllib3
from markupsafe import Markup
from odoo import models, fields, api
from odoo.exceptions import UserError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ProxmoxServer(models.Model):
    _name = 'z.proxmox.server'
    _description = 'Proxmox Server'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Server Name', required=True, tracking=True)
    host = fields.Char(string='Host / IP', required=True, tracking=True)
    port = fields.Integer(string='Port', default=8006, required=True)
    server_type = fields.Selection([
        ('standalone', 'Standalone'),
        ('cluster', 'Cluster'),
    ], string='Type', default='standalone', required=True, tracking=True)
    auth_type = fields.Selection([
        ('password', 'Password'),
        ('api_token', 'API Token'),
    ], string='Authentication', default='api_token', required=True)
    username = fields.Char(string='Username', help='e.g. root@pam')
    password = fields.Char(string='Password')
    token_id = fields.Char(string='Token ID', help='e.g. root@pam!monitor')
    token_secret = fields.Char(string='Token Secret')
    verify_ssl = fields.Boolean(string='Verify SSL', default=False)
    state = fields.Selection([
        ('draft', 'Not Connected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='Status', default='draft', readonly=True, tracking=True)
    last_check = fields.Datetime(string='Last Check', readonly=True)
    notes = fields.Text(string='Notes')
    cluster_name = fields.Char(string='Cluster Name', readonly=True)
    node_count = fields.Integer(string='Node Count', readonly=True)
    vm_ids = fields.One2many('z.proxmox.vm', 'server_id', string='Virtual Machines')
    vm_count = fields.Integer(string='VM Count', compute='_compute_vm_count')

    @api.depends('vm_ids')
    def _compute_vm_count(self):
        for rec in self:
            rec.vm_count = len(rec.vm_ids)

    def _get_base_url(self):
        return f"https://{self.host}:{self.port}/api2/json"

    def _get_auth_headers(self):
        if self.auth_type == 'api_token':
            if not self.token_id or not self.token_secret:
                raise UserError("API Token ID and Secret are required.")
            return {'Authorization': f'PVEAPIToken={self.token_id}={self.token_secret}'}
        elif self.auth_type == 'password':
            if not self.username or not self.password:
                raise UserError("Username and Password are required.")
            url = f"{self._get_base_url()}/access/ticket"
            resp = requests.post(url, data={
                'username': self.username,
                'password': self.password,
            }, verify=self.verify_ssl, timeout=10)
            if resp.status_code != 200:
                raise UserError(f"Authentication failed: {resp.text}")
            data = resp.json()['data']
            return {
                'Cookie': f"PVEAuthCookie={data['ticket']}",
                'CSRFPreventionToken': data['CSRFPreventionToken'],
            }

    def action_test_connection(self):
        for rec in self:
            try:
                headers = rec._get_auth_headers()
                url = f"{rec._get_base_url()}/version"
                resp = requests.get(url, headers=headers, verify=rec.verify_ssl, timeout=10)
                if resp.status_code == 200:
                    version_data = resp.json().get('data', {})
                    version_str = version_data.get('version', 'unknown')
                    vals = {
                        'state': 'connected',
                        'last_check': fields.Datetime.now(),
                    }
                    if rec.server_type == 'cluster':
                        cluster_url = f"{rec._get_base_url()}/cluster/status"
                        cluster_resp = requests.get(
                            cluster_url, headers=headers,
                            verify=rec.verify_ssl, timeout=10
                        )
                        if cluster_resp.status_code == 200:
                            cluster_data = cluster_resp.json().get('data', [])
                            cluster_info = next(
                                (i for i in cluster_data if i.get('type') == 'cluster'), None
                            )
                            if cluster_info:
                                vals['cluster_name'] = cluster_info.get('name', '')
                            vals['node_count'] = sum(
                                1 for i in cluster_data if i.get('type') == 'node'
                            )
                    rec.write(vals)
                    rec.message_post(
                        body=Markup(
                            "<b>Connection test successful</b><br/>"
                            "PVE Version: %s<br/>"
                            "Host: %s:%s"
                        ) % (version_str, rec.host, rec.port),
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                else:
                    rec.write({
                        'state': 'error',
                        'last_check': fields.Datetime.now(),
                    })
                    rec.message_post(
                        body=Markup(
                            "<b>Connection test failed</b><br/>"
                            "HTTP %s: %s"
                        ) % (resp.status_code, resp.text),
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                    raise UserError(f"Connection failed (HTTP {resp.status_code}): {resp.text}")
            except requests.exceptions.ConnectionError as e:
                rec.write({
                    'state': 'error',
                    'last_check': fields.Datetime.now(),
                })
                rec.message_post(
                    body=Markup("<b>Connection test failed</b><br/>Connection error: %s") % str(e),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                raise UserError(f"Connection error: {e}")
            except requests.exceptions.Timeout:
                rec.write({
                    'state': 'error',
                    'last_check': fields.Datetime.now(),
                })
                rec.message_post(
                    body=Markup("<b>Connection test failed</b><br/>Connection timed out."),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                raise UserError("Connection timed out.")

    def action_sync_vms(self):
        VmModel = self.env['z.proxmox.vm']
        for rec in self:
            if rec.state != 'connected':
                raise UserError("Please test connection first before syncing VMs.")
            try:
                headers = rec._get_auth_headers()
                nodes_url = f"{rec._get_base_url()}/nodes"
                nodes_resp = requests.get(nodes_url, headers=headers, verify=rec.verify_ssl, timeout=15)
                if nodes_resp.status_code != 200:
                    raise UserError(f"Failed to fetch nodes: {nodes_resp.text}")
                nodes = nodes_resp.json().get('data', [])

                synced_vm_ids = []
                errors = []
                for node_info in nodes:
                    node_name = node_info.get('node')
                    vms_url = f"{rec._get_base_url()}/nodes/{node_name}/qemu"
                    vms_resp = requests.get(vms_url, headers=headers, verify=rec.verify_ssl, timeout=15)
                    if vms_resp.status_code == 403:
                        errors.append(f"Node '{node_name}': Access denied (HTTP 403). Check token permissions (need VM.Audit).")
                        continue
                    if vms_resp.status_code != 200:
                        errors.append(f"Node '{node_name}': HTTP {vms_resp.status_code}")
                        continue
                    vms_data = vms_resp.json().get('data', [])

                    for vm in vms_data:
                        vmid = vm.get('vmid')
                        config_url = f"{rec._get_base_url()}/nodes/{node_name}/qemu/{vmid}/config"
                        config_resp = requests.get(config_url, headers=headers, verify=rec.verify_ssl, timeout=15)
                        config = config_resp.json().get('data', {}) if config_resp.status_code == 200 else {}

                        disk_lines = []
                        for key, val in sorted(config.items()):
                            if key.startswith(('scsi', 'virtio', 'ide', 'sata')) and key[-1].isdigit():
                                disk_lines.append(f"{key}: {val}")

                        net0_val = config.get('net0', '')
                        agent_val = config.get('agent', '0')
                        qemu_agent = '1' in str(agent_val).split(',')[0]

                        vm_status = vm.get('status', 'unknown')
                        if vm_status not in ('running', 'stopped', 'paused', 'suspended'):
                            vm_status = 'unknown'

                        vals = {
                            'server_id': rec.id,
                            'vmid': vmid,
                            'name': vm.get('name', ''),
                            'node': node_name,
                            'status': vm_status,
                            'cpu_cores': config.get('cores', 0),
                            'cpu_sockets': config.get('sockets', 1),
                            'cpu_type': config.get('cpu', ''),
                            'memory_mb': config.get('memory', 0),
                            'scsihw': config.get('scsihw', ''),
                            'qemu_agent': qemu_agent,
                            'os_type': config.get('ostype', ''),
                            'machine_type': config.get('machine', ''),
                            'bios': config.get('bios', 'seabios'),
                            'boot_order': config.get('boot', ''),
                            'net0': net0_val,
                            'disk_info': '\n'.join(disk_lines) if disk_lines else '',
                            'tags': config.get('tags', ''),
                            'description': config.get('description', ''),
                            'last_sync': fields.Datetime.now(),
                            'active': True,
                        }

                        existing = VmModel.with_context(active_test=False).search([
                            ('server_id', '=', rec.id),
                            ('vmid', '=', vmid),
                            ('node', '=', node_name),
                        ], limit=1)
                        if existing:
                            existing.write(vals)
                            vm_rec = existing
                            synced_vm_ids.append(existing.id)
                        else:
                            vm_rec = VmModel.create(vals)
                            synced_vm_ids.append(vm_rec.id)

                        # Fetch network info via QEMU Guest Agent
                        if qemu_agent and vm_status == 'running':
                            # Collect MACs from Proxmox config (net0, net1, ...)
                            pve_macs = set()
                            for key, val in config.items():
                                if key.startswith('net') and key[3:].isdigit():
                                    # Formats:
                                    # "virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,..."
                                    # "e1000=AA:BB:CC:DD:EE:FF,bridge=vmbr0,..."
                                    # Find all MAC-like patterns in the value
                                    import re
                                    macs_found = re.findall(
                                        r'([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})',
                                        str(val)
                                    )
                                    for m in macs_found:
                                        pve_macs.add(m.lower())

                            net_url = f"{rec._get_base_url()}/nodes/{node_name}/qemu/{vmid}/agent/network-get-interfaces"
                            import logging
                            _logger = logging.getLogger(__name__)
                            try:
                                net_resp = requests.get(net_url, headers=headers, verify=rec.verify_ssl, timeout=10)
                                if net_resp.status_code == 200:
                                    net_data = net_resp.json().get('data', {}).get('result', [])
                                    NicModel = self.env['z.proxmox.vm.nic']
                                    vm_rec.nic_ids.unlink()
                                    if not net_data:
                                        _logger.warning(
                                            "VM %s (%s): guest agent returned empty network data. "
                                            "pve_macs=%s", vmid, vm.get('name', ''), pve_macs
                                        )
                                    for iface in net_data:
                                        mac = iface.get('hardware-address', '').lower()
                                        # Only include interfaces whose MAC matches Proxmox-provisioned NICs
                                        if mac not in pve_macs:
                                            continue
                                        iface_name = iface.get('name', '')
                                        ip_list = []
                                        for addr in iface.get('ip-addresses', []):
                                            ip = addr.get('ip-address', '')
                                            prefix = addr.get('prefix', '')
                                            ip_type = addr.get('ip-address-type', '')
                                            if ip:
                                                ip_list.append(f"{ip}/{prefix} ({ip_type})")
                                        NicModel.create({
                                            'vm_id': vm_rec.id,
                                            'name': iface_name,
                                            'mac_address': mac,
                                            'ip_addresses': '\n'.join(ip_list) if ip_list else '',
                                        })
                                else:
                                    _logger.warning(
                                        "VM %s (%s): guest agent network-get-interfaces returned HTTP %s: %s",
                                        vmid, vm.get('name', ''), net_resp.status_code, net_resp.text[:200]
                                    )
                            except Exception as e:
                                _logger.warning(
                                    "VM %s (%s): failed to fetch network info: %s",
                                    vmid, vm.get('name', ''), str(e)
                                )

                archived = VmModel.search([
                    ('server_id', '=', rec.id),
                    ('id', 'not in', synced_vm_ids),
                ])
                if archived:
                    archived.write({'active': False})
                    archived_names = ', '.join(
                        f"{v.vmid} ({v.name})" for v in archived
                    )
                    rec.message_post(
                        body=Markup("<b>VMs archived</b> (no longer found in Proxmox):<br/>%s") % archived_names,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )

                if not synced_vm_ids:
                    err_msg = "Sync completed but 0 VMs found.\n\n"
                    if errors:
                        err_msg += "\n".join(errors)
                    else:
                        err_msg += (
                            "Possible causes:\n"
                            "- API Token has 'Privilege Separation' enabled but no permissions assigned.\n"
                            "- Token needs at least VM.Audit role on path '/'.\n\n"
                            "Fix: In Proxmox → Datacenter → Permissions → Add:\n"
                            "  Path: /\n"
                            "  User/Token: your-token (e.g. root@pam!monitor)\n"
                            "  Role: PVEAuditor\n\n"
                            "Or recreate the token with 'Privilege Separation' unchecked."
                        )
                    rec.message_post(
                        body=Markup("<b>VM Sync failed</b><br/><pre>%s</pre>") % err_msg,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                    raise UserError(err_msg)

                log_body = Markup("<b>VM Sync completed</b><br/>Synced: %s VM(s)") % len(synced_vm_ids)
                if errors:
                    log_body += Markup("<br/><br/>Warnings:<br/>%s") % Markup("<br/>").join(errors)
                rec.message_post(
                    body=log_body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

            except requests.exceptions.ConnectionError as e:
                rec.message_post(
                    body=Markup("<b>VM Sync failed</b><br/>Connection error: %s") % str(e),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                raise UserError(f"Connection error during sync: {e}")
            except requests.exceptions.Timeout:
                rec.message_post(
                    body=Markup("<b>VM Sync failed</b><br/>Connection timed out."),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                raise UserError("Connection timed out during VM sync.")

        msg = f'Successfully synced {len(synced_vm_ids)} VM(s) from Proxmox.'
        if errors:
            msg += f'\n\nWarnings:\n' + '\n'.join(errors)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Complete',
                'message': msg,
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            }
        }

    def action_view_vms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'VMs - {self.name}',
            'res_model': 'z.proxmox.vm',
            'view_mode': 'list,form',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id},
        }

    def action_reset_draft(self):
        self.write({'state': 'draft'})
