//
// Hacks for the ticket page.
//

$(function () {
    let stage_quick_links = {
        'Needs Triage': '/query?stage=Unreviewed&status=!closed&order=priority',
        'Needs PR Review': '/query?has_patch=1&needs_better_patch=0&needs_docs=0&needs_tests=0&stage=Accepted&status=!closed&order=changetime&desc=1',
        'Waiting On Author': '/query?has_patch=1&needs_better_patch=1&stage=Accepted&status=!closed&order=priority',
        'Ready For Merger': '/query?stage=Ready+for+checkin&status=!closed&order=priority',
        'Release Blockers': '/query?severity=Release+blocker&status=assigned&status=new&order=version&col=id&col=summary&col=owner&col=component&col=version&col=changetime&col=has_patch',
    }

    $('#query').after(
      "<div id='query-quick-links'>" +
        '<p>Quick Links</p>' +
        '<ul>' +
        Object.keys(stage_quick_links).map(function (stage) {
            console.log(stage, stage_quick_links[stage]);
            return '<li><a href="' + stage_quick_links[stage] + '">' + stage + '</a></li>';
        }).join('') +
        '</ul>' +
      '</div>',
    );
});
