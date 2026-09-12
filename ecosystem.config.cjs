module.exports = {
  apps: [
    {
      name: "race-reminder-bot",
      script: "main.py",
      interpreter: ".venv/bin/python",
      cwd: __dirname,
      autorestart: true,
      restart_delay: 3000,
      max_restarts: 10,
      min_uptime: "10s",
      time: true,
      out_file: "./logs/pm2-out.log",
      error_file: "./logs/pm2-error.log",
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
