/**
 * Help Command Module
 * Handles the /help command which displays available commands
 */

import { getAllHelpText } from './helpUtils.js';

function buildHelpCard(commands) {
  const entries = Object.entries(commands)
    .filter(([, cmd]) => typeof cmd?.getHelpText === 'function')
    .sort(([a], [b]) => a.localeCompare(b));

  const items = entries.map(([name, cmd]) => {
    const helpText = cmd.getHelpText();
    const description = helpText.includes(' - ')
      ? helpText.split(' - ').slice(1).join(' - ')
      : helpText.replace(/^•\s*/, '').replace(new RegExp(`^/${name}\\s*`), '').trim();

    return `
      <div class="chat-help-item">
        <code class="chat-help-item__command">/${name}</code>
        <span class="chat-help-item__desc">${description || 'Command available'}</span>
      </div>
    `;
  }).join('');

  return `
    <div class="chat-help-card">
      <div class="chat-help-card__title">Available commands</div>
      <div class="chat-help-list">${items}</div>
    </div>
  `.trim();
}

// Define the functions first
function executeHelp(socket, displayLocalMessage, arg) {
  // Access commands from the global registry at runtime (avoids circular dependency)
  const commands = window.ragotModules?.commandHandler?.commands;
  if (!commands) {
    displayLocalMessage('Error: Command system not initialized');
    return;
  }

  const allHelp = getAllHelpText(commands);
  if (!allHelp.trim()) {
    displayLocalMessage('No slash commands are available right now.', { icon: 'lightbulb' });
    return;
  }

  displayLocalMessage(buildHelpCard(commands), {
    isHtml: true,
    persist: true,
    icon: 'lightbulb'
  });
}

function getHelpHelpText() {
  return '• /help             Show this help message';
}

// Export the command object
export const help = {
  description: "Displays a list of available slash commands and their descriptions.",
  execute: executeHelp,
  getHelpText: getHelpHelpText
};
