//
// Hacks for the ticket page.
//

$(function() {
    // Don't collapse ticket properties.
    $("#modify").parent().removeClass('collapsed');
    
    //
    // Link field names to the corresponding sections in the Triaging doc.
    //

    var linkMap = {
        "h_stage": "triage-stages",
        "h_ui_ux": "ui-ux",
        "h_version": "version",
        "h_component": "component",
        "h_severity": "severity",
        "h_needs_docs": "needs-documentation",
        "h_needs_better_patch": "patch-needs-improvement",
        "h_cc": "cc",
        "h_has_patch": "has-patch",
        "h_easy": "easy-pickings",
        "h_keywords": "keywords",
        "h_needs_tests": "needs-tests"
    }

    $("table.properties th").each(function(){
        var $this = $(this);
        var anchor = linkMap[$this.attr("id")];
        if (anchor) {
            $this.wrapInner(function(){
                return "<a href='https://docs.djangoproject.com/en/dev/internals/contributing/triaging-tickets/#" + anchor + "' target='_blank'></a>";
            });
        }
    });

    //
    // Show extra user info in the change history and attachment data.
    //

    // To avoid doing lots of XHRs, grab a list of everyone who's listed in
    // a ticket comment or an attachment.
    var users = [];

    // Tickets first:
    var attribution_regex = /by (\S+)/;
    $('#changelog h3.change').each(function() { 
        users.push(this.innerHTML.match(attribution_regex)[1]);
    });

    // Attachment are easier:
    $("#attachments div dt em").each(function() { 
        users.push($(this).text());
    });

    // Make an XHR to grab info about the users, then stuff that info into
    // the comments and attachments.
    var params = $.param({'user': $.makeArray(users)}, true);
    $.getJSON("https://www.djangoproject.com/accounts/_trac/userinfo/?"+params, function (data) {
        
        // Add "(core developer)" to comments by core devs.
        $('#changelog h3.change').each(function() {
            var username = this.innerHTML.match(attribution_regex)[1];
            if (data[username] !== undefined) {
                if (data[username].core) {
                    $(this).append("<span class='core'>(core developer)</span>");
                }
            }
        });

        // Add "(cla on file)" to attachments with CLAs.
        $("#attachments div dt em").each(function() {
            var username = $(this).text();
            if (data[username] !== undefined) {
                if (data[username].cla) {
                    $(this).after(" <span class='cla'>(cla on file)</span> ");
                }
            }
        });
    });
});