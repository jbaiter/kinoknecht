var active_ajax = 0;
var vfiles = []; //TODO: Global variable, ugly, even in JavaScript -_-

function refreshIfDone() {
    if (active_ajax == 0) {
        console.debug('All AJAX Requests finished!');
    }
}

$(document).ready(function(){
    // Set up facybox links
    $("a[rel*=facybox]").facybox({modal: true})
    // Alternating colors for entry rows
    $(".entryrow:even").addClass('striped');
});


$(function() {

    $(this).ajaxSend(function(evt, request, settings) {
        active_ajax++;
        console.debug('AJAX Event no' + active_ajax + ' started');
    });
    $(this).ajaxSuccess(function(evt, request, settings) {
        console.debug('AJAX Event no' + active_ajax + ' succeeded');
        active_ajax--;
        if (active_ajax == 0) {
            console.debug('All done!');
            console.debug(settings.url);
            if (settings.url == $SCRIPT_ROOT + '/_create') {
                window.location.reload();
            } else if (settings.url == $SCRIPT_ROOT + '/_add_to_show') {
                console.debug(request.responseHTML);
                window.location.href = $SCRIPT_ROOT + '/details/show/' + request.response;
            }
        }
    });


    $('input[name="tickall"]').bind('click', function() {
        console.debug('clicked!' + $(this).attr('checked'));
        if ($(this).attr('checked')) {
            $('input[name="edittick"]').attr('checked', 'checked');
        } else{
            $('input[name="edittick"]').removeAttr('checked');
        }
    });

    $("a#moviemulti").bind('click', function() {
            vfiles = [];
            $('input[name="edittick"]:checked').each(function() {
                vfiles.push($(this).val());
            });
    });

    $("a#showmulti").bind('click', function() {
            vfiles = [];
            $('input[name="edittick"]:checked').each(function() {
                vfiles.push($(this).val());
            });
    });

    $('a.createmovie').bind('click', function() {
        // Stores the videofile id for later movie creation
        // TODO: There's got to be some other way...
        vfiles = [$(this).parents('.entryrow').attr('id')];
        $.getJSON($SCRIPT_ROOT + '/_get_clean_name', {
            vfid: vfiles[0]
        }, function(data) {
            console.debug(data);
            $('input[name="imdbquery"]').val(data);
        });
    });

    $('a#imdb_query').live('click', function() {
        // Get list of imdb entries for search string
        $.getJSON($SCRIPT_ROOT + '/_query_imdb', {
            // As facybox clones our div, we have to select the last item
            searchstr: $('input[name="imdbquery"]:last').val()
        }, function(data) {
            // Empty the results before getting new ones
            $("ul#imdb_results").last().empty();
            // Create a list item for every result entry
            $.each(data, function(key, val) {
                $("ul#imdb_results").last().append('<a href="#" class="createlink" id="' + val.imdbid + '"><li class="imdbentry">' + val.title + '</li></a>');
            });
        });
        return false;
    });

    $('a.createlink').live('click', function() {
        // Create movie from vfile and imdbid on server
        $.post($SCRIPT_ROOT + '/_create',
            {
                type: 'movie',
                vfiles: vfiles,
                imdbid: $(this).attr('id')
            }
        );
        return false;
    });

    $('a#show_query').live('click', function() {
        // Get list of shows matching search query
        $.getJSON($SCRIPT_ROOT + '/_query', {
            type: 'show',
            searchstr: $('input[name="showquery"]:last').val()
        }, function(data) {
            // Empty results before getting new ones
            $("ul#show_results").last().empty();
            // Create list item for each result entry
            $.each(data, function(key, val) {
                $("ul#show_results").last().append('<a href="#" class="addlink" id="'+val.id+'"><li>' + val.title + '</li></a>');
            });
        });
        return false;
    });

    $('a.addtoshow').bind('click', function() {
        // Stores the videofile for later episode creation
        // FIXME: Global variable insanity. REFACTOR!
        vfiles = [$(this).parents('.entryrow').attr('id')];
    });

    $('a.addlink').live('click', function() {
        // Creates an episode and adds it to the selected show
        // FIXME: Another global variable... I hate JavaScript!
        anchor = this;
        for (idx in vfiles) {
            console.debug(vfiles[idx]);
            $.post($SCRIPT_ROOT + '/_create', {
                type: 'episode',
                vfiles: [vfiles[idx]]
            }, function(data) {
                $.post($SCRIPT_ROOT + '/_add_to_show', {
                    episodeids: [data],
                    showid: $(anchor).attr('id')
                });
            });
            console.debug(document.readyState);
        }
    });

    $('a#new_show').live('click', function() {
        $(this).after(
            '<input type="text" size="15" name="newshowname"><a href=#new_show id=createshow>create</a>'
        );
    });

    $('a#createshow').live('click', function() {
        $.post($SCRIPT_ROOT + '/_create', {
            type: 'show',
            title: $('input[name="newshowname"]').val()
        }, function(data) {
            var showid = data;
            for (idx in vfiles) {
                $.post($SCRIPT_ROOT + '/_create', {
                    type: 'episode',
                    vfiles: [vfiles[idx]]
                }, function(data) {
                    $.post($SCRIPT_ROOT + '/_add_to_show', {
                        episodeids: [data],
                        showid: showid
                    });
                });
            }
        });
    });
});
