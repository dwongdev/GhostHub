/**
 * Help Utilities Module
 * Provides helper functions for generating help text dynamically
 * Separated from index.js to avoid circular dependencies
 */

/**
 * Get all help text from all registered commands
 * @param {Object} commands - The commands object from index.js
 * @returns {string} Combined help text from all commands
 */
export function getAllHelpText(commands) {
  return Object.values(commands)
    .map(cmd => cmd.getHelpText())
    .join('\n');
}
