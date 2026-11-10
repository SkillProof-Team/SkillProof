const { chromium } = require('playwright');

exports.launchBrowser = () => chromium.launch({
  headless: true,
  args: ['--no-proxy-server'],
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
    : {}),
});
