from odoo import http
from odoo.http import request


class InfraHubDashboard(http.Controller):

    @http.route('/infra_hub/dashboard_data', type='jsonrpc', auth='user')
    def dashboard_data(self):
        # Proxmox
        PveServer = request.env['z.proxmox.server']
        PveVm = request.env['z.proxmox.vm']

        pve_servers = PveServer.search([])
        vms_all = PveVm.with_context(active_test=False).search([])
        vms_active = vms_all.filtered(lambda v: v.active)

        # NPM
        NpmServer = request.env['z.npm.server']
        NpmHost = request.env['z.npm.proxy.host']

        npm_servers = NpmServer.search([])
        hosts_all = NpmHost.with_context(active_test=False).search([])
        hosts_active = hosts_all.filtered(lambda h: h.active)

        return {
            'proxmox': {
                'servers': {
                    'total': len(pve_servers),
                    'connected': len(pve_servers.filtered(lambda s: s.state == 'connected')),
                    'error': len(pve_servers.filtered(lambda s: s.state == 'error')),
                },
                'vms': {
                    'total': len(vms_active),
                    'running': len(vms_active.filtered(lambda v: v.status == 'running')),
                    'stopped': len(vms_active.filtered(lambda v: v.status == 'stopped')),
                    'archived': len(vms_all.filtered(lambda v: not v.active)),
                },
                'agent': {
                    'enabled': len(vms_active.filtered(lambda v: v.qemu_agent)),
                    'disabled': len(vms_active.filtered(lambda v: not v.qemu_agent)),
                },
            },
            'npm': {
                'servers': {
                    'total': len(npm_servers),
                    'connected': len(npm_servers.filtered(lambda s: s.state == 'connected')),
                    'error': len(npm_servers.filtered(lambda s: s.state == 'error')),
                },
                'hosts': {
                    'total': len(hosts_active),
                    'enabled': len(hosts_active.filtered(lambda h: h.enabled)),
                    'disabled': len(hosts_active.filtered(lambda h: not h.enabled)),
                    'ssl': len(hosts_active.filtered(lambda h: h.ssl_enabled)),
                    'no_ssl': len(hosts_active.filtered(lambda h: not h.ssl_enabled)),
                    'archived': len(hosts_all.filtered(lambda h: not h.active)),
                },
            },
        }
