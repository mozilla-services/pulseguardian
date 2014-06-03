$(document).ready(function() {


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
            window.location.href = res.redirect;
          },
          error: function(xhr, status, err) {
            navigator.id.logout();
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
            alert("Logout failure: " + err);
          }
        });
      }
    });
});