#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// Detect Claude config file location based on OS
function getClaudeConfigPath() {
  const platform = os.platform();
  const homeDir = os.homedir();

  if (platform === 'darwin') {
    return path.join(homeDir, 'Library/Application Support/Claude/claude_desktop_config.json');
  } else if (platform === 'win32') {
    // Check if running in WSL
    try {
      execSync('uname -r', { encoding: 'utf8' }).includes('microsoft');
      // WSL - use Windows path
      const username = process.env.USER || 'User';
      return `/mnt/c/Users/${username}/AppData/Roaming/Claude/claude_desktop_config.json`;
    } catch {
      // Native Windows
      return path.join(process.env.APPDATA, 'Claude/claude_desktop_config.json');
    }
  } else {
    // Linux
    return path.join(homeDir, '.config/Claude/claude_desktop_config.json');
  }
}

// Check if Docker is available
function checkDockerAvailable() {
  try {
    execSync('docker --version', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

// Read Claude config
function readClaudeConfig(configPath) {
  try {
    if (!fs.existsSync(configPath)) {
      // Create config directory if it doesn't exist
      const configDir = path.dirname(configPath);
      if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
      }
      return { mcpServers: {} };
    }
    const content = fs.readFileSync(configPath, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    console.error(`Error reading Claude config: ${error.message}`);
    return { mcpServers: {} };
  }
}

// Write Claude config
function writeClaudeConfig(configPath, config) {
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
    return true;
  } catch (error) {
    console.error(`Error writing Claude config: ${error.message}`);
    return false;
  }
}

// Setup Faulkner DB MCP server
function setup() {
  console.log('🔧 Faulkner DB MCP Server Setup\n');

  // Check Docker
  if (!checkDockerAvailable()) {
    console.warn('⚠️  Warning: Docker not found. Faulkner DB requires Docker to run.');
    console.log('   Please install Docker: https://docs.docker.com/get-docker/\n');
  }

  const configPath = getClaudeConfigPath();
  console.log(`📍 Claude config: ${configPath}\n`);

  let config = readClaudeConfig(configPath);

  // Add Faulkner DB MCP server
  if (!config.mcpServers) {
    config.mcpServers = {};
  }

  if (config.mcpServers['faulkner-db']) {
    console.log('✅ Faulkner DB MCP server already configured');
    return;
  }

  // Detect Python path
  let pythonPath = 'python3';
  try {
    execSync('python3 --version', { stdio: 'ignore' });
  } catch {
    try {
      execSync('python --version', { stdio: 'ignore' });
      pythonPath = 'python';
    } catch {
      console.error('❌ Python 3.8+ not found. Please install Python.');
      process.exit(1);
    }
  }

  config.mcpServers['faulkner-db'] = {
    command: pythonPath,
    args: ['-m', 'mcp_server.server'],
    env: {
      PYTHONPATH: '/home/platano/project/faulkner-db',
      FALKORDB_HOST: 'localhost',
      FALKORDB_PORT: '6379'
    }
  };

  if (writeClaudeConfig(configPath, config)) {
    console.log('✅ Faulkner DB MCP server added to Claude config');
    console.log('\n📋 Next steps:');
    console.log('   1. Clone the repository:');
    console.log('      git clone https://github.com/platano78/faulkner-db.git');
    console.log('   2. Start the Docker stack:');
    console.log('      cd faulkner-db/docker && docker-compose up -d');
    console.log('   3. Restart Claude Desktop/Code');
    console.log('   4. Verify with: npx faulkner-db-config status\n');
  }
}

// Check status
function status() {
  console.log('🔍 Faulkner DB Status\n');

  const configPath = getClaudeConfigPath();
  const config = readClaudeConfig(configPath);

  console.log(`📍 Claude config: ${configPath}`);
  console.log(`🐳 Docker available: ${checkDockerAvailable() ? 'Yes' : 'No'}`);
  console.log(`⚙️  MCP configured: ${config.mcpServers?.['faulkner-db'] ? 'Yes' : 'No'}\n`);

  if (config.mcpServers?.['faulkner-db']) {
    console.log('Configuration:');
    console.log(JSON.stringify(config.mcpServers['faulkner-db'], null, 2));
  }
}

// Remove configuration
function remove() {
  console.log('🗑️  Removing Faulkner DB from Claude config\n');

  const configPath = getClaudeConfigPath();
  let config = readClaudeConfig(configPath);

  if (config.mcpServers?.['faulkner-db']) {
    delete config.mcpServers['faulkner-db'];
    if (writeClaudeConfig(configPath, config)) {
      console.log('✅ Faulkner DB removed from Claude config');
      console.log('   Restart Claude Desktop/Code for changes to take effect.\n');
    }
  } else {
    console.log('ℹ️  Faulkner DB was not configured\n');
  }
}

// Main
const args = process.argv.slice(2);
const command = args[0] || 'setup';

if (command === '--check-only') {
  // Silent check for postinstall
  const configPath = getClaudeConfigPath();
  const config = readClaudeConfig(configPath);
  process.exit(config.mcpServers?.['faulkner-db'] ? 0 : 1);
}

switch (command) {
  case 'setup':
    setup();
    break;
  case 'status':
    status();
    break;
  case 'remove':
    remove();
    break;
  default:
    console.log('Usage: npx faulkner-db-config [setup|status|remove]');
    process.exit(1);
}
