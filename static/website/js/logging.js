
$(document).ready(function() {

    $(".like-button").click(function(e) {
        const likeButton = $(this);
        const dislikeButton = $(this).siblings(".dislike-button");
        $.ajax({
            url: likeButton.attr("url"),
            method: "POST",
            success: function(data) {
                likeButton.toggleClass("active");

                if (likeButton.hasClass("active") == dislikeButton.hasClass("active")) {
                    dislikeButton.removeClass("active");
                }
            }
        });
    });

    $(".dislike-button").click(function(e) {
        const dislikeButton = $(this);
        const likeButton = $(this).siblings(".like-button");
        $.ajax({
            url: dislikeButton.attr("url"),
            method: "POST",
            success: function(data) {
                dislikeButton.toggleClass("active");

                if (likeButton.hasClass("active") == dislikeButton.hasClass("active")) {
                    likeButton.removeClass("active");
                }
            }
        });
    });
    
});