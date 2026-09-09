import re
from odoo import models, fields, api


class NpmProxyHost(models.Model):
    _name = 'z.npm.proxy.host'
    _description = 'NPM Proxy Host'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'domain_names'

    active = fields.Boolean(string='Active', default=True)
    server_id = fields.Many2one('z.npm.server', string='NPM Server', required=True, ondelete='cascade')
    npm_id = fields.Integer(string='NPM Host ID')
    domain_names = fields.Text(string='Domain Names')
    forward_host = fields.Char(string='Forward Host')
    forward_port = fields.Integer(string='Forward Port')
    linked_vm_id = fields.Many2one(
        'z.proxmox.vm', string='Linked VM',
        compute='_compute_linked_vm', store=True,
    )
    forward_scheme = fields.Selection([
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
    ], string='Forward Scheme', default='http')
    ssl_enabled = fields.Boolean(string='SSL Enabled')
    ssl_forced = fields.Boolean(string='SSL Forced')
    ssl_provider = fields.Char(string='SSL Provider')
    http2_support = fields.Boolean(string='HTTP/2 Support')
    hsts_enabled = fields.Boolean(string='HSTS Enabled')
    hsts_subdomains = fields.Boolean(string='HSTS Subdomains')
    block_exploits = fields.Boolean(string='Block Exploits')
    caching_enabled = fields.Boolean(string='Caching Enabled')
    websocket_support = fields.Boolean(string='WebSocket Support')
    access_list_id = fields.Integer(string='Access List ID')
    advanced_config = fields.Text(string='Advanced Config')
    enabled = fields.Boolean(string='Enabled', default=True, tracking=True)
    meta_dns_challenge = fields.Boolean(string='DNS Challenge')
    last_sync = fields.Datetime(string='Last Sync', readonly=True)

    _unique_host_per_server = models.Constraint(
        'unique(server_id, npm_id)',
        'Proxy host must be unique per NPM server.',
    )

    @api.depends('forward_host')
    def _compute_linked_vm(self):
        NicModel = self.env['z.proxmox.vm.nic']
        for rec in self:
            rec.linked_vm_id = False
            if not rec.forward_host:
                continue
            ip = rec.forward_host.strip()
            # Search NICs where ip_addresses contains this IP
            nics = NicModel.search([('ip_addresses', 'ilike', ip)])
            for nic in nics:
                # Verify exact IP match (not substring)
                for line in (nic.ip_addresses or '').split('\n'):
                    # format: "192.168.0.10/24 (ipv4)"
                    match = re.match(r'^([\d\.]+)/', line.strip())
                    if match and match.group(1) == ip:
                        rec.linked_vm_id = nic.vm_id.id
                        break
                if rec.linked_vm_id:
                    break

    def _compute_display_name(self):
        for rec in self:
            domains = (rec.domain_names or '').replace('\n', ', ')
            rec.display_name = domains or f"Host #{rec.npm_id}"
