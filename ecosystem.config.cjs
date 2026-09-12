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
    {
      name: "race-reminder-deploy-watch",
      script: "scripts/deploy_watch.sh",
      interpreter: "bash",
      cwd: __dirname,
      autorestart: true,
      restart_delay: 10000,
      time: true,
      out_file: "./logs/pm2-deploy-watch-out.log",
      error_file: "./logs/pm2-deploy-watch-error.log",
      env: {
        APP_NAME: "race-reminder-bot",
        BRANCH: "main",
        DEPLOY_WATCH_INTERVAL: "60",
      },
    },
  ],
};
