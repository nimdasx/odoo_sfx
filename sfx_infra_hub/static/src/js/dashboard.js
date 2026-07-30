/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class InfraHubDashboard extends Component {
    static template = "sfx_infra_hub.Dashboard";

    setup() {
        this.action = useService("action");

        this.state = useState({
            data: {
                proxmox: {
                    servers: { total: 0, connected: 0, error: 0 },
                    vms: { total: 0, running: 0, stopped: 0, archived: 0 },
                    agent: { enabled: 0, disabled: 0 },
                },
                npm: {
                    servers: { total: 0, connected: 0, error: 0 },
                    hosts: { total: 0, enabled: 0, disabled: 0, ssl: 0, no_ssl: 0, archived: 0 },
                },
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const result = await rpc("/infra_hub/dashboard_data", {});
        this.state.data = result;
    }

    onCardClick(section, type, filter) {
        if (section === "proxmox") {
            if (type === "server") {
                let domain = [];
                if (filter === "connected") domain = [["state", "=", "connected"]];
                else if (filter === "error") domain = [["state", "=", "error"]];
                this.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Proxmox Servers",
                    res_model: "z.proxmox.server",
                    view_mode: "list,form",
                    views: [[false, "list"], [false, "form"]],
                    domain: domain,
                });
            } else if (type === "vm") {
                let domain = [];
                let context = {};
                if (filter === "running") domain = [["status", "=", "running"]];
                else if (filter === "stopped") domain = [["status", "=", "stopped"]];
                else if (filter === "archived") {
                    domain = [["active", "=", false]];
                    context = { active_test: false };
                }
                else if (filter === "agent_on") domain = [["qemu_agent", "=", true]];
                else if (filter === "agent_off") domain = [["qemu_agent", "=", false]];
                this.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Virtual Machines",
                    res_model: "z.proxmox.vm",
                    view_mode: "list,form",
                    views: [[false, "list"], [false, "form"]],
                    domain: domain,
                    context: context,
                });
            }
        } else if (section === "npm") {
            if (type === "server") {
                let domain = [];
                if (filter === "connected") domain = [["state", "=", "connected"]];
                else if (filter === "error") domain = [["state", "=", "error"]];
                this.action.doAction({
                    type: "ir.actions.act_window",
                    name: "NPM Servers",
                    res_model: "z.npm.server",
                    view_mode: "list,form",
                    views: [[false, "list"], [false, "form"]],
                    domain: domain,
                });
            } else if (type === "host") {
                let domain = [];
                let context = {};
                if (filter === "enabled") domain = [["enabled", "=", true]];
                else if (filter === "disabled") domain = [["enabled", "=", false]];
                else if (filter === "ssl") domain = [["ssl_enabled", "=", true]];
                else if (filter === "no_ssl") domain = [["ssl_enabled", "=", false]];
                else if (filter === "archived") {
                    domain = [["active", "=", false]];
                    context = { active_test: false };
                }
                this.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Proxy Hosts",
                    res_model: "z.npm.proxy.host",
                    view_mode: "list,form",
                    views: [[false, "list"], [false, "form"]],
                    domain: domain,
                    context: context,
                });
            }
        }
    }
}

registry.category("actions").add("sfx_infra_hub.dashboard", InfraHubDashboard);
