import requests
import urllib3
from markupsafe import Markup
from odoo import models, fields, api
from odoo.exceptions import UserError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NpmServer(models.Model):
    _name = 'z.npm.server'
    _description = 'Nginx Proxy Manager Server'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Server Name', required=True, tracking=True)
    url = fields.Char(
        string='URL', required=True, tracking=True,
        help='e.g. http://192.168.0.13:81'
    )
    email = fields.Char(string='Email', required=True, help='NPM admin email for login')
    password = fields.Char(string='Password', required=True)
    verify_ssl = fields.Boolean(string='Verify SSL', default=False)
    state = fields.Selection([
        ('draft', 'Not Connected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='Status', default='draft', readonly=True, tracking=True)
    last_check = fields.Datetime(string='Last Check', readonly=True)
    notes = fields.Text(string='Notes')
    proxy_host_ids = fields.One2many('z.npm.proxy.host', 'server_id', string='Proxy Hosts')
    proxy_host_count = fields.Integer(string='Proxy Host Count', compute='_compute_proxy_host_count')

    @api.depends('proxy_host_ids')
    def _compute_proxy_host_count(self):
        for rec in self:
            rec.proxy_host_count = len(rec.proxy_host_ids)

    def _get_base_url(self):
        base = self.url.rstrip('/')
        return f"{base}/api"

    def _get_token(self):
        url = f"{self._get_base_url()}/tokens"
        resp = requests.post(url, json={
            'identity': self.email,
            'secret': self.password,
        }, verify=self.verify_ssl, timeout=10)
        if resp.status_code != 200:
            raise UserError(f"Authentication failed (HTTP {resp.status_code}): {resp.text}")
        data = resp.json()
        return data.get('token')

    def _get_auth_headers(self):
        token = self._get_token()
        return {'Authorization': f'Bearer {token}'}

    def action_test_connection(self):
        for rec in self:
            try:
                headers = rec._get_auth_headers()
                url = f"{rec._get_base_url()}/nginx/proxy-hosts"
                resp = requests.get(url, headers=headers, verify=rec.verify_ssl, timeout=10)
                if resp.status_code == 200:
                    rec.write({
                        'state': 'connected',
                        'last_check': fields.Datetime.now(),
                    })
                    rec.message_post(
                        body=Markup(
                            "<b>Connection test successful</b><br/>"
                            "URL: %s"
                        ) % rec.url,
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

    def action_sync_proxy_hosts(self):
        HostModel = self.env['z.npm.proxy.host']
        for rec in self:
            if rec.state != 'connected':
                raise UserError("Please test connection first before syncing proxy hosts.")
            try:
                headers = rec._get_auth_headers()
                url = f"{rec._get_base_url()}/nginx/proxy-hosts"
                resp = requests.get(url, headers=headers, verify=rec.verify_ssl, timeout=15)
                if resp.status_code != 200:
                    rec.message_post(
                        body=Markup("<b>Proxy Host Sync failed</b><br/>HTTP %s: %s") % (resp.status_code, resp.text),
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                    raise UserError(f"Failed to fetch proxy hosts (HTTP {resp.status_code}): {resp.text}")

                hosts_data = resp.json()
                synced_ids = []

                for host in hosts_data:
                    npm_id = host.get('id')
                    domain_list = host.get('domain_names', [])
                    ssl = host.get('ssl', {}) or {}
                    meta = host.get('meta', {}) or {}

                    vals = {
                        'server_id': rec.id,
                        'npm_id': npm_id,
                        'domain_names': '\n'.join(domain_list) if domain_list else '',
                        'forward_host': host.get('forward_host', ''),
                        'forward_port': host.get('forward_port', 0),
                        'forward_scheme': host.get('forward_scheme', 'http'),
                        'ssl_enabled': bool(host.get('certificate_id')),
                        'ssl_forced': bool(host.get('ssl_forced')),
                        'ssl_provider': ssl.get('provider', '') if isinstance(ssl, dict) else '',
                        'http2_support': bool(host.get('http2_support')),
                        'hsts_enabled': bool(host.get('hsts_enabled')),
                        'hsts_subdomains': bool(host.get('hsts_subdomains')),
                        'block_exploits': bool(host.get('block_exploits')),
                        'caching_enabled': bool(host.get('caching_enabled')),
                        'websocket_support': bool(host.get('allow_websocket_upgrade')),
                        'access_list_id': host.get('access_list_id', 0),
                        'advanced_config': host.get('advanced_config', ''),
                        'enabled': bool(host.get('enabled')),
                        'meta_dns_challenge': bool(meta.get('dns_challenge')) if isinstance(meta, dict) else False,
                        'last_sync': fields.Datetime.now(),
                        'active': True,
                    }

                    existing = HostModel.with_context(active_test=False).search([
                        ('server_id', '=', rec.id),
                        ('npm_id', '=', npm_id),
                    ], limit=1)
                    if existing:
                        existing.write(vals)
                        synced_ids.append(existing.id)
                    else:
                        new_host = HostModel.create(vals)
                        synced_ids.append(new_host.id)

                # Archive hosts no longer in NPM
                archived = HostModel.search([
                    ('server_id', '=', rec.id),
                    ('id', 'not in', synced_ids),
                ])
                if archived:
                    archived.write({'active': False})
                    archived_names = ', '.join(
                        (h.domain_names or '').split('\n')[0] or f"#{h.npm_id}" for h in archived
                    )
                    rec.message_post(
                        body=Markup("<b>Proxy hosts archived</b> (no longer in NPM):<br/>%s") % archived_names,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )

                if not synced_ids:
                    raise UserError("Sync completed but 0 proxy hosts found. Check NPM permissions.")

                rec.message_post(
                    body=Markup("<b>Proxy Host Sync completed</b><br/>Synced: %s host(s)") % len(synced_ids),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

            except requests.exceptions.ConnectionError as e:
                rec.message_post(
                    body=Markup("<b>Proxy Host Sync failed</b><br/>Connection error: %s") % str(e),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                raise UserError(f"Connection error during sync: {e}")
            except requests.exceptions.Timeout:
                rec.message_post(
                    body=Markup("<b>Proxy Host Sync failed</b><br/>Connection timed out."),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                raise UserError("Connection timed out during proxy host sync.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Complete',
                'message': f'Successfully synced {len(synced_ids)} proxy host(s).',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_proxy_hosts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Proxy Hosts - {self.name}',
            'res_model': 'z.npm.proxy.host',
            'view_mode': 'list,form',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id},
        }

    def action_reset_draft(self):
        self.write({'state': 'draft'})
