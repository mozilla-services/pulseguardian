var errorMessage = function(msg) {
    error_bar.text(msg);
    error_bar.slideDown(300).delay(3000).slideUp(300);
};

$(document).ready(function() {
    error_bar = $('#error-bar');

    // Signin/Signout callbacks
    var signinLink = $('#signin-link').click(function() {
        navigator.id.request();
    });


    var signoutLink = $('#signout-link').click(function() {
        navigator.id.logout();
    });


    // WIP: watching login/logout
    var currentUser = $('#user').data('email') || null;


    navigator.id.watch({
      loggedInUser: currentUser,
      onlogin: function(assertion) {
        $.ajax({
          type: 'POST',
          url: '/auth/login',
          data: {assertion: assertion},
          success: function(res, status, xhr) {
            if (res.ok) {
                window.location.href = res.redirect;
            } else {
                errorMessage("Login error: " + res.message);
            }
          },
          error: function(xhr, status, err) {
            errorMessage("Login failure: " + err);
          }
        });
      },
      onlogout: function() {
        $.ajax({
          type: 'POST',
          url: '/auth/logout',
          success: function(res, status, xhr) {
            window.location.reload();
          },
          error: function(xhr, status, err) {
            errorMessage("Logout failure: " + err);
          }
        });
      }
    });
});