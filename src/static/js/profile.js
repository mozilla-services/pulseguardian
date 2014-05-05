$(document).ready(function() {
    var error_bar = $('#error-bar');

    $('.delete').click(function() {
        var queue = $(this).closest('.queue');
        var queue_name = queue.data('queue-name');
        $.ajax({
            url: '/queue/' + queue_name,
            type: 'DELETE',
            success: function(result) {
                if (result.ok) {
                    $(queue).slideUp(300);
                } else {
                    error_bar.text("Couldn't delete queue '" + queue_name + "'");
                    error_bar.show(300).delay(3000).hide(300);
                }
            }
        });
    })
});