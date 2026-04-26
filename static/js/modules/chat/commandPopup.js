/**
 * Command Popup Module
 * Handles the popup UI for slash commands
 */

import { Component, Module, createElement, css, attr, $, $$ } from '../../libs/ragot.esm.min.js';
import { scheduleAutofocus } from '../../utils/focusManager.js';

let chatInput = null;
let commandSelected = false;
let inputLifecycle = null;

const listItemTouchState = {
    isTouching: false,
    tapThreshold: 10
};

function shouldKeepChatOpenForCommand(command) {
    return command?.keepChatOpen === true;
}

class CommandPopupComponent extends Component {
    constructor(inputElement) {
        super();
        this.chatInput = inputElement;
        this.isDragging = false;
        this.hasManualPosition = false;
        this.dragOffset = { x: 0, y: 0 };
        this.closeArmed = false;
        this.closeArmTimeout = null;
        this.mountAnimTimeout = null;
        this.unmountTimeout = null;
    }

    render() {
        return createElement('div', { className: 'command-popup', 'aria-label': 'Command suggestions' },
            createElement('div', { className: 'command-popup-header' },
                createElement('span', { id: 'command-popup-title', textContent: 'Available Commands' }),
                createElement('button', {
                    type: 'button',
                    'aria-label': 'Close command suggestions',
                    onClick: (e) => {
                        e.stopPropagation();
                        hideCommandPopup();
                    },
                    textContent: 'x'
                })
            ),
            createElement('div', {
                className: 'command-popup-list',
                role: 'listbox',
                id: 'command-popup-list',
                'aria-labelledby': 'command-popup-title',
                style: window.ragotModules?.appRuntime?.MOBILE_DEVICE ? { maxHeight: '180px' } : {}
            })
        );
    }

    onStart() {
        const header = $('.command-popup-header', this.element);

        this.on(document, 'mousemove', this.drag);
        this.on(document, 'mouseup', this.stopDrag);
        this.on(document, 'touchmove', this.dragTouch, { passive: false });
        this.on(document, 'touchend', this.stopDragTouch);

        this.on(header, 'mousedown', this.startDrag);
        this.on(header, 'touchstart', this.startDragTouch, { passive: false });

        this.on(document, 'click', this.handleOutsideClick);
        this.on(window, 'resize', this.handleViewportChange);
        this.on(window, 'orientationchange', this.handleViewportChange);
        if (window.visualViewport) {
            this.on(window.visualViewport, 'resize', this.handleViewportChange);
            this.on(window.visualViewport, 'scroll', this.handleViewportChange);
        }

        this.positionNearInput(true);

        this.closeArmTimeout = setTimeout(() => {
            this.closeArmed = true;
            this.closeArmTimeout = null;
        }, 100);

        this.mountAnimTimeout = setTimeout(() => {
            if (this.element) {
                css(this.element, { opacity: '1', transform: 'translateY(0)' });
            }
            this.mountAnimTimeout = null;
        }, 10);
    }

    onStop() {
        this.clearTimers();
        this.isDragging = false;
        this.closeArmed = false;
    }

    clearTimers() {
        if (this.closeArmTimeout) {
            clearTimeout(this.closeArmTimeout);
            this.closeArmTimeout = null;
        }
        if (this.mountAnimTimeout) {
            clearTimeout(this.mountAnimTimeout);
            this.mountAnimTimeout = null;
        }
        if (this.unmountTimeout) {
            clearTimeout(this.unmountTimeout);
            this.unmountTimeout = null;
        }
    }

    scheduleUnmount() {
        if (!this.element) {
            this.unmount();
            return;
        }

        css(this.element, { opacity: '0', transform: 'translateY(10px) translateZ(0)' });
        this.unmountTimeout = setTimeout(() => {
            this.unmount();
            this.unmountTimeout = null;
        }, 200);
    }

    startDrag = (e) => {
        if (e.target.closest('button')) return;
        this.isDragging = true;
        this.hasManualPosition = true;
        const rect = this.element.getBoundingClientRect();
        this.dragOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top };
        this.element.classList.add('dragging');
        e.preventDefault();
        e.stopPropagation();
    };

    startDragTouch = (e) => {
        if (e.target.closest('button')) return;
        this.isDragging = true;
        this.hasManualPosition = true;
        const rect = this.element.getBoundingClientRect();
        this.dragOffset = { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
        this.element.classList.add('dragging');
        e.preventDefault();
        e.stopPropagation();
    };

    drag = (e) => {
        if (!this.isDragging || !this.element) return;
        requestAnimationFrame(() => {
            this.updatePosition(e.clientX - this.dragOffset.x, e.clientY - this.dragOffset.y);
        });
        e.preventDefault();
    };

    dragTouch = (e) => {
        if (!this.isDragging || !this.element) return;
        requestAnimationFrame(() => {
            this.updatePosition(e.touches[0].clientX - this.dragOffset.x, e.touches[0].clientY - this.dragOffset.y);
        });
        e.preventDefault();
    };

    stopDrag = () => {
        this.isDragging = false;
        if (this.element) this.element.classList.remove('dragging');
    };

    stopDragTouch = () => {
        this.isDragging = false;
        if (this.element) this.element.classList.remove('dragging');
    };

    updatePosition(x, y) {
        if (!this.element) return;
        const pw = this.element.offsetWidth;
        const ph = this.element.offsetHeight;
        const cx = Math.max(0, Math.min(x, window.innerWidth - pw));
        const cy = Math.max(0, Math.min(y, window.innerHeight - ph));
        css(this.element, {
            position: 'fixed',
            left: `${cx}px`,
            top: `${cy}px`,
            bottom: 'auto',
            transform: 'translateZ(0)'
        });
    }

    handleViewportChange = () => {
        this.positionNearInput();
    };

    positionNearInput(force = false) {
        if (!this.element || !this.chatInput) return;
        if (this.hasManualPosition && !force) return;

        const inputRect = this.chatInput.getBoundingClientRect();
        const chatRect = this.chatInput.closest('#chat-container')?.getBoundingClientRect();
        const viewport = window.visualViewport;
        const vw = viewport?.width || window.innerWidth;
        const vh = viewport?.height || window.innerHeight;
        const topOffset = viewport?.offsetTop || 0;
        const leftOffset = viewport?.offsetLeft || 0;

        const popupWidth = this.element.offsetWidth || Math.min(320, vw - 24);
        const popupHeight = this.element.offsetHeight || 200;
        const margin = 8;

        let left = (chatRect?.left ?? inputRect.left) + leftOffset;
        left = Math.max(leftOffset + margin, Math.min(left, leftOffset + vw - popupWidth - margin));

        const aboveTop = topOffset + inputRect.top - popupHeight - margin;
        const belowTop = topOffset + inputRect.bottom + margin;
        const canFitAbove = aboveTop >= topOffset + margin;
        const canFitBelow = belowTop + popupHeight <= topOffset + vh - margin;
        let top = canFitAbove ? aboveTop : (canFitBelow ? belowTop : Math.max(topOffset + margin, topOffset + vh - popupHeight - margin));

        css(this.element, {
            position: 'fixed',
            left: `${Math.round(left)}px`,
            top: `${Math.round(top)}px`,
            right: 'auto',
            bottom: 'auto',
            transform: 'translateZ(0)'
        });
    }

    handleOutsideClick = (e) => {
        if (!this.closeArmed || !this.element) return;
        if (!this.element.contains(e.target) && e.target !== this.chatInput) {
            hideCommandPopup();
        }
    };
}

let popupComponent = null;

export function initCommandPopup(inputElement) {
    if (!inputLifecycle) {
        inputLifecycle = new Module().start();
    }
    updateInput(inputElement);

    return {
        showCommandPopup,
        hideCommandPopup,
        isPopupVisible: () => !!popupComponent,
        set input(el) { updateInput(el); }
    };
}

function updateInput(el) {
    if (chatInput === el) return;

    if (inputLifecycle) {
        inputLifecycle.stop().start(); // Reset all listeners
    }

    chatInput = el;
    if (!el) return;
    attr(chatInput, {
        'aria-controls': 'command-popup-list',
        'aria-expanded': 'false'
    });

    const onInput = () => {
        const val = chatInput.value;
        if (!val.startsWith('/')) {
            commandSelected = false;
            if (popupComponent) hideCommandPopup();
            return;
        }
        const hasSpace = val.includes(' ');
        if (commandSelected && !hasSpace && val.length > 1) commandSelected = false;
        if (val === '/') {
            commandSelected = false;
            if (!popupComponent) showCommandPopup();
            filterAndDisplayCommands('');
            return;
        }
        if (commandSelected && hasSpace) {
            if (popupComponent) hideCommandPopup();
            return;
        }
        if (!hasSpace) {
            if (!popupComponent) showCommandPopup();
            filterAndDisplayCommands(val.substring(1));
        } else if (popupComponent) {
            hideCommandPopup();
        }
    };

    const onKeyDown = (e) => {
        if (!popupComponent) return;
        if (e.key === 'Escape' || ((e.key === 'Backspace' || e.key === 'Delete') && chatInput.value === '/')) {
            e.preventDefault();
            hideCommandPopup();
        } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
            e.preventDefault();
            navigateHighlight(e.key === 'ArrowDown' ? 1 : -1);
        } else if (e.key === 'Tab' || e.key === 'Enter') {
            e.preventDefault();
            selectHighlighted();
        }
    };

    const onFocus = () => {
        if (chatInput.value === '/') showCommandPopup();
    };

    inputLifecycle.on(chatInput, 'input', onInput);
    inputLifecycle.on(chatInput, 'keydown', onKeyDown);
    inputLifecycle.on(chatInput, 'focus', onFocus);

    if (popupComponent) {
        popupComponent.chatInput = el;
    }
}

export function showCommandPopup() {
    if (!chatInput) return;
    if (popupComponent) {
        hideCommandPopup();
    }

    const appState = window.ragotModules?.appState;
    if (appState) {
        appState.navigationDisabled = true;
    }

    popupComponent = new CommandPopupComponent(chatInput);
    popupComponent.mount(document.body);
    attr(chatInput, { 'aria-expanded': 'true' });
    popupComponent.positionNearInput(true);
    filterAndDisplayCommands('');
}

export function hideCommandPopup() {
    if (!popupComponent) return;

    const appState = window.ragotModules?.appState;
    if (appState) {
        appState.navigationDisabled = false;
    }

    const closing = popupComponent;
    popupComponent = null;
    if (chatInput) {
        attr(chatInput, {
            'aria-expanded': 'false'
        });
    }
    closing.scheduleUnmount();
}

function getPopupElement() {
    return popupComponent?.element || null;
}

function filterAndDisplayCommands(filterText = '') {
    const commandPopup = getPopupElement();
    if (!commandPopup) return;

    const commandList = $('.command-popup-list', commandPopup);
    if (!commandList) return;

    commandList.innerHTML = '';

    const allCommands = Object.entries(window.ragotModules?.commandHandler?.commands || {});
    let clean = filterText.toLowerCase().trim();
    while (clean.startsWith('/')) clean = clean.substring(1);

    const filtered = allCommands.filter(([name, cmd]) =>
        name.toLowerCase().startsWith(clean) ||
        (cmd?.name && cmd.name.toLowerCase().startsWith(clean))
    );

    filtered.sort(([a], [b]) => {
        const la = a.toLowerCase();
        const lb = b.toLowerCase();
        if (la === clean && lb !== clean) return -1;
        if (la !== clean && lb === clean) return 1;
        if (la.length !== lb.length) return la.length - lb.length;
        return la.localeCompare(lb);
    });

    if (filtered.length === 0) {
        commandList.appendChild(createElement('div', { className: 'no-results', textContent: 'No commands match' }));
        popupComponent?.positionNearInput();
        return;
    }

    filtered.forEach(([name, cmd]) => {
        if (typeof cmd.getHelpText !== 'function') {
            console.warn(`Command /${name} is missing getHelpText method`);
            return;
        }

        const helpText = cmd.getHelpText();
        const descPart = helpText.includes(' - ') ? helpText.split(' - ')[1] : helpText;

        let touchStartY = 0;
        let touchStartTime = 0;
        let hasMoved = false;

        const item = createElement('div', {
            id: `command-option-${name}`,
            role: 'option',
            tabindex: '-1',
            'aria-selected': 'false',
            dataset: { commandName: name, commandHelpText: helpText },
            events: {
                touchstart: (e) => {
                    touchStartY = e.touches[0].clientY;
                    touchStartTime = Date.now();
                    hasMoved = false;
                    listItemTouchState.isTouching = true;
                },
                touchmove: (e) => {
                    if (Math.abs(e.touches[0].clientY - touchStartY) > listItemTouchState.tapThreshold) {
                        hasMoved = true;
                    }
                },
                touchend: (e) => {
                    listItemTouchState.isTouching = false;
                    if (!hasMoved && Date.now() - touchStartTime < 300) {
                        e.preventDefault();
                        selectCommand(name, helpText);
                    }
                },
                click: (e) => {
                    if (!listItemTouchState.isTouching) {
                        e.preventDefault();
                        e.stopPropagation();
                        selectCommand(name, helpText);
                    }
                }
            }
        },
            createElement('div', { textContent: `/${name}` }),
            createElement('div', { textContent: descPart })
        );

        commandList.appendChild(item);
    });

    const items = $$(':scope > div:not(.no-results)', commandList);
    if (items.length > 0) {
        applyHighlightedItem(items, 0);
    }

    attr(commandList, {
        onScroll: () => {
            const allItems = $$(':scope > div.highlighted', commandList);
            allItems.forEach(el => el.classList.remove('highlighted'));
            attr(commandList, { onScroll: null });
        }
    });

    popupComponent?.positionNearInput();
}

function navigateHighlight(direction) {
    const commandPopup = getPopupElement();
    const items = commandPopup ? $$('.command-popup-list > div:not(.no-results)', commandPopup) : null;
    if (!items || items.length === 0) return;

    let current = -1;
    items.forEach((item, i) => {
        if (item.classList.contains('highlighted')) current = i;
    });

    let next = current + direction;
    if (next < 0) next = items.length - 1;
    if (next >= items.length) next = 0;

    applyHighlightedItem(items, next);
}

function selectHighlighted() {
    const commandPopup = getPopupElement();
    const highlighted = commandPopup ? $('.command-popup-list > div.highlighted', commandPopup) : null;
    if (highlighted?.dataset.commandName) {
        selectCommand(highlighted.dataset.commandName, highlighted.dataset.commandHelpText);
    } else {
        hideCommandPopup();
    }
}

function applyHighlightedItem(items, index) {
    items.forEach((item, i) => {
        const highlighted = i === index;
        item.classList.toggle('highlighted', highlighted);
        item.setAttribute('aria-selected', highlighted ? 'true' : 'false');
        if (highlighted) {
            item.scrollIntoView({ block: 'nearest' });
        }
    });
}

function selectCommand(name, helpText) {
    commandSelected = true;

    const chatContainer = $('#chat-container');
    if (chatContainer?.classList.contains('collapsed')) {
        if (window.ragotModules?.chatManager?.expandChat) {
            window.ragotModules.chatManager.expandChat();
        } else if (chatContainer.classList.contains('collapsed')) {
            chatContainer.classList.replace('collapsed', 'expanded');
        }
    }

    const hasArgs = helpText.includes('{') || helpText.includes('[') ||
        helpText.toLowerCase().includes('optional') || helpText.includes('<');

    if (hasArgs) {
        chatInput.value = `/${name} `;
        scheduleAutofocus(chatInput, { frames: 2, selectionBehavior: 'cursor-end' });
    } else {
        chatInput.value = `/${name}`;
        let processed = false;
        try {
            processed = window.ragotModules?.commandHandler?.processCommand?.(chatInput.value) ?? false;
        } catch (err) {
            console.error(`Error auto-processing command /${name}:`, err);
        }
        if (processed) {
            const command = window.ragotModules?.commandHandler?.commands?.[name];
            if (!shouldKeepChatOpenForCommand(command)) {
                window.ragotModules?.chatManager?.collapseChat?.();
            }
            chatInput.value = '';
        } else {
            scheduleAutofocus(chatInput, { frames: 2 });
        }
    }

    hideCommandPopup();
}
