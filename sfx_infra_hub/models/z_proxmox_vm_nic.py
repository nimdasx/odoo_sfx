from odoo import models, fields


class ProxmoxVmNic(models.Model):
    _name = 'z.proxmox.vm.nic'
    _description = 'Proxmox VM Network Interface'
    _order = 'name'

    vm_id = fields.Many2one('z.proxmox.vm', string='Virtual Machine', required=True, ondelete='cascade')
    name = fields.Char(string='Interface Name')
    mac_address = fields.Char(string='MAC Address')
    ip_addresses = fields.Text(string='IP Addresses')
