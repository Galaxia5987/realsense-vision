function setDeep(obj, path, value) {
    const parts = path.split(".");
    let cur = obj;
    for (let i = 0; i < parts.length - 1; i++) {
        if (!(parts[i] in cur)) cur[parts[i]] = {};
        cur = cur[parts[i]];
    }
    cur[parts[parts.length - 1]] = value;
}

function submitFormJson() {
    const data = {};

    $("#configForm").find(":input[name]").each(function() {
        const $el = $(this);
        let value;

        if ($el.is(":checkbox")) {
            value = $el.is(":checked");
        } else {
            value = $el.val();
        }

        setDeep(data, $el.attr("name"), value);
    });

    data["pipeline"]["args"] = data["pipeline"]["args"].split(",").filter(arg => arg.trim() !== "");

    $.ajax({
        url: "/update_config",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify(data),
    });
}

cancelIntervalId = -1;

$(document).ready(function() {
    $("#configForm").on("submit", function(e) {
        e.preventDefault();
        submitFormJson();
    });

    $("#colorStreamToggle").on("change", function() {
        const target = $("#colorStreamImage");

        if ($(this).is(":checked")) {
            target.removeClass("d-none");
        } else {
            target.addClass("d-none");
        }
    });

    $("#depthStreamToggle").on("change", function() {
        const target = $("#depthStreamImage");

        if ($(this).is(":checked")) {
            target.removeClass("d-none");
        } else {
            target.addClass("d-none");
        }
    });

    const term = new Terminal({
        fontFamily: 'monospace',
        fontSize: 14,
        convertEol: true,
        wrapAround: false
    });

    term.open(document.getElementById('logTerminal'));

    function updateVisibleLog(text) {
        // clear visible screen, keep scrollback
        term.write('\x1b[2J');
        term.write('\x1b[H');
        term.write(text.replace(/\n/g, '\r\n'));
    }

    // Optional polling loop
    async function pollLogs() {
        const res = await fetch('/logs'); // change to your endpoint
        const txt = await res.text();
        updateVisibleLog(txt);
    }

    cancelIntervalId = setInterval(pollLogs, 1000);
    pollLogs();

    $("#logSettingsBtn").on("click", function() {
            bootbox.dialog({
            title: "Log Settings",
            message: `
                <form id="logSettingsForm">
                    <div class="form-group mb-2">
                        <label for="logLevel">Log Level</label>
                        <select class="form-control" id="logLevel">
                            <option ${logSettings.level === "DEBUG" ? "selected" : ""} value="DEBUG">DEBUG</option>
                            <option ${logSettings.level === "INFO" ? "selected" : ""} value="INFO">INFO</option>
                            <option ${logSettings.level === "WARNING" ? "selected" : ""} value="WARNING">WARNING</option>
                            <option ${logSettings.level === "ERROR" ? "selected" : ""} value="ERROR">ERROR</option>
                            <option ${logSettings.level === "CRITICAL" ? "selected" : ""} value="CRITICAL">CRITICAL</option>
                        </select>
                    </div>
                    <div class="form-group mb-2">
                        <label for="pollInterval">Log Poll Interval (ms)</label>
                        <input type="number" class="form-control" id="pollInterval" value="${logSettings.interval}">
                    </div>
                    <div class="form-check mb-2">
                        <input type="checkbox" class="form-check-input" id="disableLogs" ${logSettings.disabled ? "checked" : ""}>
                        <label class="form-check-label" for="disableLogs">Disable Logs</label>
                    </div>
                    <button type="button" class="btn btn-secondary" id="refreshLogBtn">Refresh Log</button>
                </form>
            `,
            buttons: {
                save: {
                    label: "Save",
                    className: "btn-primary",
                    callback: function() {
                        const settings = {
                            level: $('#logLevel').val(),
                            interval: parseInt($('#pollInterval').val()),
                            disabled: $('#disableLogs').is(':checked')
                        };
                        if (settings.interval != logSettings.interval ||
                            settings.disabled != logSettings.disabled) {
                            if (cancelIntervalId != -1) {
                                clearInterval(cancelIntervalId);
                            }
                            if (!settings.disabled) {
                                cancelIntervalId = setInterval(pollLogs, settings.interval);
                            }
                        }
                        if (settings.level != logSettings.level) {
                            $.post("/set_log_level", {level: settings.level})
                            .fail(() => {
                                bootbox.alert('Failed to set log level. Please try again.');
                            });
                        }
                        logSettings = settings;
                        return true;
                    }
                },
                cancel: {
                    label: "Cancel",
                    className: "btn-secondary"
                }
            }
        });
    });
    $("#refreshLogBtn").on("click", function() {
        pollLogs();
    });
});

function restartService() {
    window.location.href = "/restart";
}

function restoreConfig() {
    bootbox.confirm({
        message: 'Are you sure you want to restore the default configuration? This action cannot be undone.',
        buttons: {
            confirm: {
                label: 'Yes',
                className: 'btn-success'
            },
            cancel: {
                label: 'No',
                className: 'btn-danger'
            }
        },
        callback: function (result) {
            if (result) {
                $.post("/restore_config")
                .done(() => {
                    location.reload();
                })
                .fail(() => {
                    bootbox.alert('Failed to restore configuration. Please try again.');
                });
            }
        }
    });
}