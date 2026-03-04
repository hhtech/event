#!/usr/bin/env node
/**
 * 一键：加密 app.html → 生成 index.html → 提交并推送
 * 需先设置环境变量: APP_ENCRYPT_KEY=你的秘钥
 */
const { execSync } = require('child_process');
const path = require('path');

const key = process.env.APP_ENCRYPT_KEY || process.env.ENCRYPT_PASSWORD;
if (!key) {
  console.error('请先设置环境变量: set APP_ENCRYPT_KEY=你的秘钥');
  console.error('  Windows: set APP_ENCRYPT_KEY=你的秘钥');
  console.error('  Linux/Mac: export APP_ENCRYPT_KEY=你的秘钥');
  process.exit(1);
}

const root = path.join(__dirname);
try {
  console.log('1. 加密 app.html → index.html ...');
  execSync('node encrypt.js', { stdio: 'inherit', env: { ...process.env, APP_ENCRYPT_KEY: key } });
  console.log('2. 提交并推送 ...');
  execSync('git add index.html', { cwd: root, stdio: 'inherit' });
  execSync('git commit -m "update: 重新生成加密页面"', { cwd: root, stdio: 'inherit' });
  execSync('git push origin main', { cwd: root, stdio: 'inherit' });
  console.log('✅ 完成');
} catch (e) {
  process.exit(1);
}
