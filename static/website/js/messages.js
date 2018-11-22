/**
 * Dynamic behaviour related to showing/hiding messages.
 */



jQuery(function() {

    /**
     * Close a message
     */
    $(".message__close-button").click(function(e) {
        e.preventDefault();
        let messageContainer = $(this).parents(".message-container");
        let numMessages = messageContainer.children(".message:visible").length;
        let message = $(this).parents(".message");

        // Hide the whole container if there's only a single message
        if (numMessages == 1) {
            messageContainer.fadeOut();
        } else {
            message.fadeOut();
        }
    })
})