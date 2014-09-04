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
    function getUsername(elt) {
        // Extract the username from the given element,
        // To find a username, we look for a text node that follows
        // a <a class="timeline"> element.
        // We exclude usernames containing "@" because we want actual
        // usernames, not a "Full Name <email@...>" that trac can sometimes
        // generate.
        var raw = $('.timeline', elt)[0].nextSibling.data.trim();
        if (raw && raw.substring(0, 3) === 'by ' && raw.indexOf('@') < 0) {
            return raw.substring(3);
        }
        else {
            return '';
        }
    }

    // To avoid doing lots of XHRs, grab a list of everyone who's listed in
    // a ticket comment or an attachment.
    var users = [];

    // Tickets first:
    var attribution_regex = /by (\S+)/;
    $('#changelog h3.change').each(function() {
        var username = getUsername(this);
        if (username) {
            users.push(username);
        }
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
            var username = getUsername(this);
            if (username && data[username] && data[username].core) {
                $(this).append("<span class='core'>(core developer)</span>");
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

    // Show Pull Requests from Github with titles matching any of the following
    // patterns: "#<ticket_id> ", "#<ticket_id>,", "#<ticket_id>:", "#<ticket_id>)
    var ticket_id = window.location.pathname.split('/')[2];
    $.getJSON("https://api.github.com/search/issues?q=repo:django/django+in:title+type:pr+"
        + "%23"+ticket_id+"%20"
        + "+%23"+ticket_id+"%2C"
        + "+%23"+ticket_id+"%3A"
        + "+%23"+ticket_id+"%29",
        function(data) {
        var links = data.items.map(function(item) {
            // open or closed
            var pr_state = item.state;
            var build_state;
            var merged = false;
            var url = item.pull_request.html_url;
            var link_text = item.number;

            if (pr_state === "closed") {
                link_text = "<del>"+link_text+"</del>";
            }

            // Check if our rate limit is exceeded. If it is, just display
            // the PRs without additional infos
            var core_rate_limit_exceeded = false;
            $.ajax({
                url: "https://api.github.com/rate_limit",
                dataType: 'json',
                async: false,
                success: function (data, textStatus, xhr) {
                    // We need to perform a maximum of 3 extra requests to get status infos
                    if(data.resources.core.remaining < 3) {
                        core_rate_limit_exceeded = true;
                    }
                }
            });

            if(!core_rate_limit_exceeded) {
                // Get merge state of PR
                $.ajax({
                    url: "https://api.github.com/repos/django/django/pulls/" + item.number + "/merge",
                    dataType: 'json',
                    async: false,
                    success: function (data, textStatus, xhr) {
                        merged = true;
                    },
                    error: function (xhr) {
                        if (xhr.status === 404) {
                            merged = false;
                        }
                    }
                });

                if(!merged) {
                    // Check if the PR was merged manually
                    $.ajax({
                        url: "https://api.github.com/repos/django/django/issues/"+ item.number +"/comments",
                        dataType: 'json',
                        async: false,
                        success: function(data) {
                            $.each( data, function( index, value ) {
                                // Look for "merged/fixed in sha1..."
                                if(value.body.match(/(merged|fixed) in \b[0-9a-f]{40}\b/i)) {
                                    merged = true;
                                }
                            });
                        }
                    });
                }

                if (pr_state === 'open') {
                    // Get build state of PR if pr_state is open
                    $.ajax({
                        url: "https://api.github.com/repos/django/django/pulls/" + item.number,
                        dataType: 'json',
                        async: false,
                        success: function (data) {
                            $.ajax({
                                url: data.statuses_url,
                                dataType: 'json',
                                async: false,
                                success: function (data) {
                                    if (data.length > 0) {
                                        build_state = data[0].state;
                                        link_text += " build:" + build_state;
                                    }
                                }
                            });
                        }
                    });
                } else {
                    // if PR state is closed, display if it was merged or not
                    if (merged === true) {
                        link_text += " merged";
                    } else {
                        link_text += " unmerged";
                    }
                }
            }
            return "<a href='" + url + "'>" + link_text + "</a>";
        });

        var link = '<a href="https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/working-with-git/#publishing-work">How to create a pull request</a>';
        if (links.length > 0) {
            link = links.join(", ");
        }
        $("table.properties").append("<tr><th>Pull Requests:</th><td>" + link + "</td><tr>");
    });
});
