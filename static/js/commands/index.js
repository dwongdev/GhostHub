/**
 * Commands Index Module
 * Exports all available commands for easy registration
 */

import * as helpCommand from './help.js';
import * as myviewCommand from './myview.js';
import * as viewCommand from './view.js';
import * as randomCommand from './random.js';
import * as searchCommand from './search.js';
import * as addCommand from './add.js';
import * as playCommand from './play.js';
import * as removeCommand from './remove.js';
import * as hideCommand from './hide.js';
import * as showCommand from './show.js';
import * as unhideCommand from './unhide.js';
import * as kickCommand from './kick.js';
import { getAllHelpText as getHelp } from './helpUtils.js';

// Export all commands with their names as keys
export const commands = {
  help: helpCommand.help,
  myview: myviewCommand.myview,
  view: viewCommand.view,
  random: randomCommand.random,
  kick: kickCommand.kick,
  search: searchCommand.search,
  find: searchCommand.find, // Alias for search
  add: addCommand.add,
  play: playCommand.play,
  remove: removeCommand.remove,
  hide: hideCommand.hide,
  show: showCommand.show,
  unhide: unhideCommand.unhide
};

// Export getAllHelpText function that uses the utility
export function getAllHelpText() {
  return getHelp(commands);
}
