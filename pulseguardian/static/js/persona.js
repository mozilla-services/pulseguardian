/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

var errorMessage = function(msg) {
    error_bar.text(msg);
    error_bar.slideDown(300).delay(10000).slideUp(300);
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