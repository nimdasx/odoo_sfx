{
    'name': 'Infra Hub',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Infrastructure monitoring hub - Proxmox, Nginx Proxy Manager, and more',
    'description': """
        Infra Hub
        =========
        Centralized infrastructure monitoring:
        - Proxmox (cluster & standalone): servers, VMs, network interfaces
        - Nginx Proxy Manager (planned)
    """,
    'author': 'Sofyan Wijaya',
    'depends': ['base', 'mail'],
    'data': [
        'security/infra_hub_security.xml',
        'security/ir.model.access.csv',
        'views/dashboard_action.xml',
        'views/proxmox_server_views.xml',
        'views/proxmox_vm_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sfx_infra_hub/static/src/js/dashboard.js',
            'sfx_infra_hub/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'Other proprietary',
}
