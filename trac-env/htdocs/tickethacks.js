//
// Hacks for the ticket page.
//

$(function () {
  // Don't collapse ticket properties.
  $('#modify').parent().removeClass('collapsed');

  //
  // Link field names to the corresponding sections in the Triaging doc.
  //

  var linkMap = {
    h_stage: 'triage-stages',
    h_ui_ux: 'ui-ux',
    h_version: 'version',
    h_component: 'component',
    h_severity: 'severity',
    h_needs_docs: 'needs-documentation',
    h_needs_better_patch: 'patch-needs-improvement',
    h_cc: 'cc',
    h_has_patch: 'has-patch',
    h_easy: 'easy-pickings',
    h_keywords: 'keywords',
    h_needs_tests: 'needs-tests',
  };

  $('table.properties th').each(function () {
    var $this = $(this);
    var anchor = linkMap[$this.attr('id')];
    if (anchor) {
      $this.wrapInner(function () {
        return (
          "<a href='https://docs.djangoproject.com/en/dev/internals/contributing/triaging-tickets/#" +
          anchor +
          "' target='_blank'></a>"
        );
      });
    }
  });

  // Show Pull Requests from Github with titles matching any of the following
  // patterns: "#<ticket_id> ", "#<ticket_id>,", "#<ticket_id>:", "#<ticket_id>)
  var ticket_id = window.location.pathname.split('/')[2];
  $.getJSON(
    'https://api.github.com/search/issues?q=repo:django/django+in:title+type:pr+' +
      '%23' +
      ticket_id +
      '%20' +
      '+%23' +
      ticket_id +
      '%2C' +
      '+%23' +
      ticket_id +
      '%3A' +
      '+%23' +
      ticket_id +
      '%29',
    function (data) {
      var links = data.items.map(function (item) {
        if (item.number == ticket_id) {
          return undefined; // skip this element if PR id == ticket id
        }

        // open or closed
        var pr_state = item.state;
        var build_state;
        var merged = false;
        var url = item.pull_request.html_url;
        var link_text = item.number;

        if (pr_state === 'closed') {
          link_text = '<del>' + link_text + '</del>';
        }

        // Check if our rate limit is exceeded. If it is, just display
        // the PRs without additional infos
        var core_rate_limit_exceeded = false;
        $.ajax({
          url: 'https://api.github.com/rate_limit',
          dataType: 'json',
          async: false,
          success: function (data, textStatus, xhr) {
            // We need to perform a maximum of 3 extra requests to get status infos
            if (data.resources.core.remaining < 3) {
              core_rate_limit_exceeded = true;
            }
          },
        });

        if (!core_rate_limit_exceeded) {
          // Get merge state of PR
          $.ajax({
            url:
              'https://api.github.com/repos/django/django/pulls/' +
              item.number +
              '/merge',
            dataType: 'json',
            async: false,
            success: function (data, textStatus, xhr) {
              merged = true;
            },
            error: function (xhr) {
              if (xhr.status === 404) {
                merged = false;
              }
            },
          });

          if (!merged) {
            // Check if the PR was merged manually
            $.ajax({
              url:
                'https://api.github.com/repos/django/django/issues/' +
                item.number +
                '/comments',
              dataType: 'json',
              async: false,
              success: function (data) {
                $.each(data, function (index, value) {
                  // Look for "merged/fixed in sha1..."
                  if (value.body.match(/(merged|fixed) in \b[0-9a-f]{40}\b/i)) {
                    merged = true;
                  }
                });
              },
            });
          }

          if (pr_state === 'open') {
            // Get build state of PR if pr_state is open
            $.ajax({
              url:
                'https://api.github.com/repos/django/django/pulls/' +
                item.number,
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
                      link_text += ' build:' + build_state;
                    }
                  },
                });
              },
            });
          } else {
            // if PR state is closed, display if it was merged or not
            if (merged === true) {
              link_text += ' merged';
            } else {
              link_text += ' unmerged';
            }
          }
        }
        return "<a href='" + url + "'>" + link_text + '</a>';
      });

      var link =
        '<a href="https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/working-with-git/#publishing-work">How to create a pull request</a>';
      if (links.length > 0) {
        link = links.join(', ');
      }
      $('table.properties').append(
        '<tr><th>Pull Requests:</th><td>' + link + '</td><tr>',
      );
    },
  );

  // Ticket Triage Guidelines: show next steps based on the ticket's status,
  // flags, etc.
  function get_boolean_ticket_flag(name) {
    return (
      $('#h_' + name)
        .next()
        .text()
        .trim() === 'yes'
    );
  }
  function get_ticket_flag(name) {
    return $('#h_' + name)
      .next()
      .text()
      .trim();
  }
  var stage = get_ticket_flag('stage');
  var ticket_status = $('.trac-status').text().trim();
  var ticket_type = $('.trac-type').text().trim();
  var has_patch = get_boolean_ticket_flag('has_patch');
  var patch_needs_improvement = get_boolean_ticket_flag('needs_better_patch');
  var needs_docs = get_boolean_ticket_flag('needs_docs');
  var needs_tests = get_boolean_ticket_flag('needs_tests');
  var next_steps = [];
  var include_link_to_pr_msg =
    'include a link to the pull request in the ticket comment when making ' +
    'that update. The usual format is: <code>[https://github.com/django/django/pull/####&nbsp;PR]</code>.';
  if (ticket_status == 'closed') {
    // TODO (e.g. reopening a wontfix or needsinfo, or what to do in the
    // case of a regression caused by the ticket
  } else if (stage == 'Unreviewed') {
    next_steps.push(
      "For bugs: reproduce the bug. If it's a regression, " +
        "<a href='https://docs.djangoproject.com/en/dev/internals/contributing/triaging-tickets/#bisecting-a-regression'>" +
        'bisect</a> to find the commit where the behavior changed.',
    );
    next_steps.push(
      'For new features or cleanups: give a second opinion of the proposal.',
    );
    next_steps.push(
      'In either case, mark the Triage Stage as "Accepted" if the issue seems valid, ' +
        'ask for additional clarification from the reporter, or close the ticket.',
    );
  } else if (stage == 'Accepted') {
    if (!has_patch) {
      next_steps.push(
        "<a href='https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/submitting-patches/'>" +
          'To provide a patch</a> by sending a pull request. ' +
          "<a href='https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/submitting-patches/#claiming-tickets'>" +
          "Claim the ticket</a> when you start working so that someone else doesn't duplicate effort. " +
          "Before sending a pull request, review your work against the <a href='" +
          "https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/submitting-patches/#patch-review-checklist'>" +
          'patch review checklist</a>. ' +
          'Check the "Has patch" flag on the ticket after sending a pull request and ' +
          include_link_to_pr_msg,
      );
    } else {
      if (needs_tests) {
        next_steps.push(
          'To add tests to the patch, then uncheck the "Needs tests" flag on the ticket.',
        );
      }
      if (needs_docs) {
        next_steps.push(
          'To write documentation for the patch, then uncheck "Needs documentation" on the ticket.',
        );
      }
      if (patch_needs_improvement) {
        next_steps.push(
          'To improve the patch as described in the pull request review ' +
            'comments or on this ticket, then uncheck "Patch needs improvement".',
        );
      }
      if (!needs_tests && !needs_docs && !patch_needs_improvement) {
        next_steps.push(
          'For anyone except the patch author to review the patch using the ' +
            '<a href="https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/submitting-patches/#patch-review-checklist">' +
            'patch review checklist</a> and either ' +
            'mark the ticket as "Ready for checkin" if everything looks good, ' +
            'or leave comments for improvement and mark the ticket as ' +
            '"Patch needs improvement".',
        );
      } else {
        next_steps.push(
          '<p>If creating a new pull request, ' + include_link_to_pr_msg,
        );
      }
    }
  } else if (stage == 'Ready for checkin') {
    next_steps.push(
      'For a Django committer to do a final review of the patch and merge ' +
        'it if all looks good.',
    );
  } else if (stage == 'Someday/Maybe') {
    next_steps.push(
      '<p>Unknown. The Someday/Maybe triage stage is used ' +
        'to keep track of high-level ideas or long term feature requests.</p>' +
        "<p>It could be an issue that's blocked until a future version of Django " +
        '(if so, Keywords will contain that version number). It could also ' +
        'be an enhancement request that we might consider adding someday to the framework ' +
        'if an excellent patch is submitted.</p>' +
        "<p>If you're interested in contributing to the issue, " +
        'raising your ideas on the <a href="https://forum.djangoproject.com/c/internals/5">Django Forum</a> ' +
        'would be a great place to start.<p>',
    );
  }
  if (next_steps.length) {
    $('#ticket').after(
      "<div id='ticket-next-steps' class='trac-content'><p>According to the " +
        "<a href='https://docs.djangoproject.com/en/dev/internals/contributing/triaging-tickets/#triage-workflow'>" +
        "ticket's flags</a>, the next step(s) to move this issue forward are:</p>" +
        '<ul><li>' +
        next_steps.join('</li><li>') +
        '</li></ul>' +
        '</div>',
    );
  }
});
