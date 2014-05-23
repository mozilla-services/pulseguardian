$(document).ready(function() {
    var error_bar = $('#error-bar');

    // Auto-reload
    var autoReload = true;
    var reloadInterval = 8000;
    setInterval(function() {
        if (autoReload) {
            $('#queues-info').load('/queues');
        }
    }, reloadInterval);
    $('.autoreload').click(function() {
        autoReload = !autoReload;
        $(this).toggleClass('inactive');
    });


    // Queue deletion
    $('.delete').click(function() {
        var queue = $(this).closest('.queue');
        var queue_name = queue.data('queue-name');
        $.ajax({
            url: '/queue/' + queue_name,
            type: 'DELETE',
            success: function(result) {
                if (!result.ok) {
                    error_bar.text("Couldn't delete queue '" + queue_name + "' in Pulse");
                    error_bar.show(300).delay(3000).hide(300);
                }

                $(queue).slideUp(300);
            }
        });
    });
});