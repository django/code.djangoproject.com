//
// Hacks for the ticket page.
//

$(function() {
    // Don't collapse ticket properties.
    $("#modify").parent().removeClass('collapsed');
    
    //
    // Show extra user info in the change history and attachment data.
    //

    // To avoid doing lots of XHRs, grab a list of everyone who's listed in
    // a ticket comment or an attachment.
    var users = [];

    // Tickets first:
    var attribution_regex = /by ([\w\-]+)/;
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
