from odoo import models, fields


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

    _sql_constraints = [
        ('unique_host_per_server', 'unique(server_id, npm_id)', 'Proxy host must be unique per NPM server.')
    ]

    def name_get(self):
        result = []
        for rec in self:
            domains = (rec.domain_names or '').replace('\n', ', ')
            result.append((rec.id, domains or f"Host #{rec.npm_id}"))
        return result
