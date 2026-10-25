const addDialog = document.querySelector('#add-dialog');
const connectionStatus = document.querySelector('#connection-status');
const playlistFile = document.querySelector('#playlist-file');
let socket;
let version = null;
let retryDelay = 500;
let requestNumber = 0;
let commandError = '';
const pending = new Map();

function showStatus(message) {
    connectionStatus.textContent = message;
    connectionStatus.hidden = !message;
    document.querySelectorAll('.dialog-status').forEach(status => {
        status.textContent = message;
        status.hidden = !message;
    });
}

function checkedIds() {
    return [...document.querySelectorAll('.station-check:checked')].map(check => check.value);
}

function updateDeleteSelected() {
    const count = checkedIds().length;
    // The button lives in the player, which is re-rendered on every state update.
    const deleteSelected = document.querySelector('[data-delete-selected]');
    deleteSelected.hidden = count === 0;
    deleteSelected.title = `Delete ${count} selected`;
    deleteSelected.setAttribute('aria-label', deleteSelected.title);
}

function sendCommand(data, onSuccess, onFinish = () => {}) {
    if (!socket || socket.readyState !== WebSocket.OPEN || version === null) {
        showStatus('Connecting to your radio. Please try again in a moment.');
        onFinish();
        return;
    }
    commandError = '';
    showStatus('');
    const requestId = ++requestNumber;
    const timeout = setTimeout(() => {
        pending.delete(requestId);
        onFinish();
        showStatus('The radio has not confirmed this action. Check the station list before trying again.');
    }, 60000);
    pending.set(requestId, { onSuccess, onFinish, timeout });
    socket.send(JSON.stringify({ ...data, request_id: requestId }));
}

function connect() {
    showStatus('Connecting to your radio…');
    socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`);
    socket.addEventListener('message', event => {
        const message = JSON.parse(event.data);
        if (message.type === 'state') {
            const focused = document.activeElement;
            const focusLabel = focused && focused.getAttribute('aria-label');
            const focusContainer = focused && focused.closest('#player-content, #station-content');
            // Keep selections across re-renders; station ids are stable database ids.
            const checked = checkedIds();
            document.querySelector('#player-content').innerHTML = message.player_html;
            document.querySelector('#station-content').innerHTML = message.stations_html;
            document.querySelectorAll('.station-check').forEach(check => { check.checked = checked.includes(check.value); });
            updateDeleteSelected();
            version = message.version;
            retryDelay = 500;
            if (focusContainer && focusLabel) {
                const target = [...focusContainer.querySelectorAll('[aria-label]')]
                    .find(element => element.getAttribute('aria-label') === focusLabel);
                if (target) target.focus({ preventScroll: true });
            }
            showStatus(commandError);
        } else if (message.type === 'ack' || message.type === 'error') {
            const command = pending.get(message.request_id);
            if (command) {
                clearTimeout(command.timeout);
                pending.delete(message.request_id);
                command.onFinish();
                if (message.type === 'ack' && command.onSuccess) command.onSuccess();
            }
            commandError = message.type === 'error' && message.request_id ? message.message : '';
            showStatus(message.type === 'error' ? message.message : '');
        }
    });
    socket.addEventListener('close', () => {
        version = null;
        const interrupted = pending.size > 0;
        pending.forEach(command => { clearTimeout(command.timeout); command.onFinish(); });
        pending.clear();
        showStatus(interrupted
            ? 'Connection lost during a command. Reconnecting to check the radio…'
            : 'Radio disconnected. Reconnecting…');
        // Never replay commands: an interrupted add may already have succeeded.
        setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 10000);
    });
    socket.addEventListener('error', () => socket.close());
}

// Delegation keeps controls working when server-rendered station rows change.
document.addEventListener('click', event => {
    const button = event.target.closest('[data-add-station], [data-add-playlist], [data-delete-selected], [data-close-dialog], [data-delete-id]');
    if (button) {
        if (button.hasAttribute('data-add-playlist')) {
            playlistFile.click();
        } else if (button.hasAttribute('data-delete-selected')) {
            sendCommand({ action: 'del_many', ids: checkedIds().join(',') });
        } else if (button.hasAttribute('data-add-station')) {
            addDialog.showModal();
            document.querySelector('#stream-url').focus();
        } else if (button.hasAttribute('data-close-dialog')) {
            button.closest('dialog').close();
        } else {
            sendCommand({ action: 'del', id: button.dataset.deleteId });
        }
        return;
    }
    const link = event.target.closest('a');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !url.searchParams.has('action')) return;
    event.preventDefault();
    sendCommand(Object.fromEntries(url.searchParams));
});

document.querySelectorAll('dialog').forEach(dialog => {
    const status = document.createElement('p');
    status.className = 'dialog-status';
    status.setAttribute('role', 'alert');
    status.hidden = true;
    dialog.querySelector('form').append(status);
    dialog.addEventListener('click', event => {
        if (event.target !== dialog) return;
        const bounds = dialog.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
    dialog.querySelector('form').addEventListener('submit', event => {
        event.preventDefault();
        const form = event.target;
        const submit = form.querySelector('[type="submit"]');
        if (submit.disabled) return;
        const data = Object.fromEntries(new FormData(form));
        submit.disabled = true;
        sendCommand(data, () => {
            dialog.close();
            if (dialog === addDialog) form.reset();
        }, () => { submit.disabled = false; });
    });
});
// The server takes the .m3u text and appends every new http(s) URL in it.
playlistFile.addEventListener('change', async () => {
    const file = playlistFile.files[0];
    if (!file) return;
    sendCommand({ action: 'add_playlist', playlist: await file.text() }, null, () => { playlistFile.value = ''; });
});
document.addEventListener('change', event => {
    if (event.target.matches('.station-check')) updateDeleteSelected();
});
connect();
