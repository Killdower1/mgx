module.exports = {
  apps: [
    {
      name: "difotoin-dashboard",
      cwd: "/var/www/difotoin-dashboard/nicegui_template",
      script: "/var/www/difotoin-dashboard/nicegui_template/.venv/bin/python",
      args: "/var/www/difotoin-dashboard/nicegui_template/main.py",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        PORT: "8502",
        DIFOTOIN_ADMIN_EMAIL: "octadimas@gmail.com",
        DIFOTOIN_ADMIN_PASSWORD: "Dowerdower1",
      },
    },
  ],
};
