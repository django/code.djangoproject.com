//
// Hacks for the ticket page.
//

$(function () {
    let stage_quick_links = {
      'Unreviewed': '/query?stage=Unreviewed&status=!closed&order=priority',
      'Needs Patch': '/query?stage=Unreviewed&status=!closed&order=priority',
      'Needs PR Review': '/query?has_patch=1&needs_better_patch=0&needs_docs=0&needs_tests=0&stage=Accepted&status=!closed&order=changetime&desc=1',
      'Waiting On Author': '/query?has_patch=1&needs_better_patch=1&stage=Accepted&status=!closed&order=priority',
      'Ready For Checkin': '/query?stage=Ready+for+checkin&status=!closed&order=priority',
    }
    let other_quick_links = {
      'Needs Info': '/query?resolution=needsinfo&order=priority',
      'Someday/Maybe': '/query?stage=Someday%2FMaybe&status=!closed&order=priority',
      'Release Blockers': '/query?severity=Release+blocker&status=assigned&status=new&order=version&col=id&col=summary&col=owner&col=component&col=version&col=changetime&col=has_patch',
    }

    $('#query').after(
      "<div id='query-quick-links'>" +
        '<span>Queues:</span>' +
        '<ul>' +
        Object.keys(stage_quick_links).map(function (stage) {
            console.log(stage, stage_quick_links[stage]);
            return '<li><a href="' + stage_quick_links[stage] + '">' + stage + '</a></li>';
        }).join('') +
        '</ul>' +
        '<span>More tickets:</span>' +
        '<ul>' +
        Object.keys(other_quick_links).map(function (stage) {
            console.log(stage, other_quick_links[stage]);
            return '<li><a href="' + other_quick_links[stage] + '">' + stage + '</a></li>';
        }).join('') +
        '</ul>' +
      '</div>',
    );
});
