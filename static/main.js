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
});

function restartService() {
    window.location.href = "/restart_service";
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