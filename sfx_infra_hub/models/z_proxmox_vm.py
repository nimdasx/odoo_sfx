from odoo import models, fields, api


class ProxmoxVm(models.Model):
    _name = 'z.proxmox.vm'
    _description = 'Proxmox Virtual Machine'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'node, vmid'

    active = fields.Boolean(string='Active', default=True)
    server_id = fields.Many2one('z.proxmox.server', string='Server', required=True, ondelete='cascade')
    vmid = fields.Integer(string='VMID', required=True)
    name = fields.Char(string='VM Name')
    node = fields.Char(string='Node')
    status = fields.Selection([
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('paused', 'Paused'),
        ('suspended', 'Suspended'),
        ('unknown', 'Unknown'),
    ], string='Status', default='unknown', tracking=True)
    cpu_cores = fields.Integer(string='CPU Cores')
    cpu_sockets = fields.Integer(string='CPU Sockets')
    cpu_type = fields.Char(string='CPU Type')
    memory_mb = fields.Integer(string='Memory (MB)')
    scsihw = fields.Selection([
        ('lsi', 'LSI 53C895A'),
        ('lsi53c810', 'LSI 53C810'),
        ('virtio-scsi-pci', 'VirtIO SCSI'),
        ('virtio-scsi-single', 'VirtIO SCSI Single'),
        ('megasas', 'MegaRAID SAS 8708EM2'),
        ('pvscsi', 'VMware PVSCSI'),
    ], string='SCSI Controller')
    qemu_agent = fields.Boolean(string='QEMU Guest Agent', tracking=True)
    os_type = fields.Selection([
        ('l24', 'Linux 2.4 Kernel'),
        ('l26', 'Linux 2.6 - 6.x Kernel'),
        ('wxp', 'Windows XP'),
        ('w2k', 'Windows 2000'),
        ('w2k3', 'Windows 2003'),
        ('w2k8', 'Windows 2008'),
        ('wvista', 'Windows Vista'),
        ('win7', 'Windows 7'),
        ('win8', 'Windows 8 / 2012'),
        ('win10', 'Windows 10 / 2016 / 2019'),
        ('win11', 'Windows 11 / 2022 / 2025'),
        ('solaris', 'Solaris / OpenSolaris'),
        ('other', 'Other'),
    ], string='OS Type')
    machine_type = fields.Char(string='Machine Type')
    bios = fields.Char(string='BIOS')
    boot_order = fields.Char(string='Boot Order')
    net0 = fields.Char(string='Network (net0)')
    disk_info = fields.Text(string='Disk Info')
    nic_ids = fields.One2many('z.proxmox.vm.nic', 'vm_id', string='Network Interfaces')
    proxy_host_ids = fields.One2many('z.npm.proxy.host', 'linked_vm_id', string='Proxy Hosts')
    tags = fields.Char(string='Tags')
    description = fields.Text(string='Description')
    last_sync = fields.Datetime(string='Last Sync', readonly=True)

    _sql_constraints = [
        ('unique_vm_per_server', 'unique(server_id, vmid, node)', 'VM must be unique per server and node.')
    ]

    def name_get(self):
        return [(rec.id, f"{rec.vmid} - {rec.name or 'Unknown'}") for rec in self]
