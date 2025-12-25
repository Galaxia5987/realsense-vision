let pipelineFormConfig = {
    schemaByType: {},
    initialType: "",
    initialProps: {}
};

function setDeep(obj, path, value) {
    const parts = path.split(".");
    let cur = obj;
    for (let i = 0; i < parts.length - 1; i++) {
        if (!(parts[i] in cur)) cur[parts[i]] = {};
        cur = cur[parts[i]];
    }
    cur[parts[parts.length - 1]] = value;
}

function readPrimitiveFormFields($formRoot) {
    const data = {};
    $formRoot.find(":input[name]").not("#propertiesForm :input").each(function() {
        const $el = $(this);
        const value = $el.is(":checkbox") ? $el.is(":checked") : $el.val();
        setDeep(data, $el.attr("name"), value);
    });
    return data;
}

function getPipelineSchema(selectedType) {
    if (!pipelineFormConfig.schemaByType) return null;
    return pipelineFormConfig.schemaByType[selectedType];
}

function readPipelineProperties(selectedType) {
    const schemaForType = getPipelineSchema(selectedType);
    const hasSchema =
        schemaForType &&
        schemaForType.schema &&
        schemaForType.schema.properties &&
        Object.keys(schemaForType.schema.properties).length > 0;

    if (hasSchema && typeof JSONForm !== "undefined") {
        return JSONForm.getFormValue($("#propertiesForm")) || {};
    }

    if (selectedType === pipelineFormConfig.initialType) {
        return pipelineFormConfig.initialProps || {};
    }

    return {};
}

function submitFormJson() {
    const data = readPrimitiveFormFields($("#configForm"));
    const selectedPipelineType = $("#pipelineTypeSelect").val();
    const props = readPipelineProperties(selectedPipelineType);
    setDeep(data, "pipeline.properties", props);

    $.ajax({
        url: "/update_config",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify(data),
    });
}

function renderPipelineProperties(selectedType) {
    const $container = $("#propertiesForm");
    const schemaForType = getPipelineSchema(selectedType);
    if (!schemaForType || _.isEmpty(schemaForType.schema?.properties)) {
        $container
            .removeData("jsonform-tree")
            .html('<p class="text-muted mb-0 small">This pipeline has no configurable properties.</p>');
        return;
    }

    $container
        .removeData("jsonform-tree")
        .empty()
        .jsonForm({
        schema: schemaForType.schema,
        form: (schemaForType.form && schemaForType.form.length) ? schemaForType.form : ["*"],
        value: selectedType === pipelineFormConfig.initialType ? pipelineFormConfig.initialProps : {}
    });
}

function initPipelineSection(options) {
    pipelineFormConfig = {
        schemaByType: options.jsonSchema || {},
        initialType: options.initialPipelineType || "",
        initialProps: options.initialPipelineProps || {}
    };

    const $pipelineSelect = $("#pipelineTypeSelect");
    const onTypeChange = () => renderPipelineProperties($pipelineSelect.val());
    $pipelineSelect.off("change.pipeline").on("change.pipeline", onTypeChange);
    onTypeChange();
}

let cancelIntervalId = -1;
const latencyClasses = ["bg-success", "bg-warning", "bg-danger", "bg-secondary"];

function updateLatencyIndicator(latencySeconds) {
    const $indicator = $("#latencyIndicator");
    if (!$indicator.length) return;

    $indicator.removeClass(latencyClasses.join(" "));

    if (latencySeconds === undefined || latencySeconds === null || isNaN(latencySeconds) || latencySeconds < 0) {
        $indicator.addClass("bg-secondary").text("Latency: --");
        return;
    }

    const latencyMs = latencySeconds * 1000;
    let badgeClass = "bg-success";
    if (latencyMs >= 200) {
        badgeClass = "bg-danger";
    } else if (latencyMs >= 120) {
        badgeClass = "bg-warning";
    }

    const latencyText = latencyMs >= 1000
        ? `${latencySeconds.toFixed(2)} s`
        : `${Math.round(latencyMs)} ms`;

    $indicator.addClass(badgeClass).text(`Latency: ${latencyText}`);
}

function showAlert(message){
    bootbox.alert({
        message: message,
        size: 'small'
    });
}

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

    function updateVisibleLog(text = "") {
        // clear visible screen, keep scrollback
        term.write('\x1b[2J');
        term.write('\x1b[H');
        term.write(text.replace(/\n/g, '\r\n'));
    }

    // Optional polling loop
    async function pollLogs(forceLatest = false) {
        if (logSettings.disabled) return;
        try {
            const res = await fetch(`/logs?force_latest=${forceLatest}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const { log, latency } = await res.json();
            if(log != "")
                updateVisibleLog(log);
            updateLatencyIndicator(latency);
        } catch (err) {
            console.error("Failed to fetch logs", err);
            updateLatencyIndicator(null);
        }
    }

    cancelIntervalId = setInterval(() => pollLogs(false), logSettings.interval || 100);
    pollLogs(true);

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

    $(document).on("click", "#refreshLogBtn", function() {
        pollLogs(true);
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
