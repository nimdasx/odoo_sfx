from odoo import http
from odoo.http import request


class InfraHubDashboard(http.Controller):

    @http.route('/infra_hub/dashboard_data', type='json', auth='user')
    def dashboard_data(self):
        ServerModel = request.env['z.proxmox.server']
        VmModel = request.env['z.proxmox.vm']

        servers = ServerModel.search([])
        vms_all = VmModel.with_context(active_test=False).search([])
        vms_active = vms_all.filtered(lambda v: v.active)

        return {
            'servers': {
                'total': len(servers),
                'connected': len(servers.filtered(lambda s: s.state == 'connected')),
                'error': len(servers.filtered(lambda s: s.state == 'error')),
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
        }
