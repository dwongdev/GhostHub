/**
 * Command Handler Module
 * Handles slash-command processing, rate limiting, and command execution.
 * Uses modular command system for easy extension.
 */

import { commands } from '../../commands/index.js';

// Rate limiting configuration
const RATE_LIMIT = {
  maxCommands: 3,
  timeWindow: 5000, // ms
  commands: []
};

// Socket reference (initialized in initCommandHandler)
let socket = null;
// Function reference for local-only system messages
let displayLocalMessage = null;

/**
 * Initialize the command handler
 * @param {Object} socketInstance        The existing socket.io instance
 * @param {Function} displayLocalMessageFn  Function to display local-only msgs
 */
export function initCommandHandler(socketInstance, displayLocalMessageFn) {
  if (!socketInstance) {
    console.error('Command handler init failed: no socket provided');
    return null;
  }
  socket = socketInstance;
  displayLocalMessage = displayLocalMessageFn;
  
  // The processCommand function is defined in this module's scope
  // and uses the module-scoped socket and displayLocalMessage.
  const handlerInstance = {
    commands,
    processCommand // Expose the processCommand function itself
  };

  console.log('Command handler initialized with modular command system and processCommand exposed.');
  return handlerInstance; // Return the instance for direct use (e.g., by chatManager)
}

/**
 * Process a chat message; if it's a slash command, execute it
 * @param {string} message - The chat input
 * @returns {boolean}      - True if handled as a command
 */
export function processCommand(message) {
  if (!message.startsWith('/')) return false;

  // Trim the message to avoid issues with extra spaces
  message = message.trim();
  
  // Fix potential double-slash issue 
  if (message.startsWith('//')) {
    message = message.replace('//', '/');
  }
  
  // Simple first pass - just get the command name
  const commandName = message.split(' ')[0].substring(1).toLowerCase();
  
  // Check if it's a valid command first
  if (!commandName || !commands[commandName]) {
    displayLocalMessage(`Unknown command: /${commandName}`);
    return true;
  }
  
  // Now parse the full command with arguments
  // Get everything after the command name as the argument
  let arg = '';
  if (message.length > commandName.length + 1) {
    // +2 accounts for the slash and the space
    arg = message.substring(commandName.length + 2).trim();
  }
  
  // Rate-limit
  const now = Date.now();
  RATE_LIMIT.commands = RATE_LIMIT.commands.filter(t => now - t < RATE_LIMIT.timeWindow);
  if (RATE_LIMIT.commands.length >= RATE_LIMIT.maxCommands) {
    displayLocalMessage('Slow down... Command rate limit exceeded');
    return true;
  }
  RATE_LIMIT.commands.push(now);

  // Execute the command
  try {
    const command = commands[commandName];

    // Validate command structure
    if (!command || typeof command.execute !== 'function') {
      console.error(`[Commands] Invalid command structure for /${commandName}:`, command);
      displayLocalMessage(`Error: Command /${commandName} is not properly configured`);
      return true;
    }

    // Log command execution for debugging
    console.log(`[Commands] Executing /${commandName} with args:`, arg || '(none)');

    command.execute(socket, displayLocalMessage, arg);
  } catch (error) {
    console.error(`[Commands] Error executing /${commandName}:`, error);
    console.error(`[Commands] Stack trace:`, error.stack);
    displayLocalMessage(`Error executing command /${commandName}: ${error.message}`);
  }

  return true;
}
