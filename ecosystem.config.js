module.exports = {
  apps: [
    {
      name: "difotoin-dashboard",
      cwd: "./streamlit_template",
      script: ".venv/bin/streamlit",
      args: "run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        PORT: "8501",
        DIFOTOIN_ADMIN_EMAIL: "octadimas@gmail.com",
        DIFOTOIN_ADMIN_PASSWORD: "Dowerdower1"
      }
    }
  ]
};
