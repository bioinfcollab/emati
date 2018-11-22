/**
 * Returns the file name in a path. E.g. the input
 *   "this/is/some/very/long/path/to/a/file.txt"
 * will return
 *   "file.txt"
 * @param {*} file_path 
 */
function basename(file_path) {
    return file_path.split('/').pop();
}


$(document).ready(function() {

    $("#settings-form").change(function(e) {
        settingsChanged();
    });


    /**
     * When clicking on the "save" button, hide the buttons
     * and show a loading icon.
     */
    $("#settings-buttons__save").click(function(e) {
        // Do not prevent the default behaviour since this
        // is what submits the form and triggers the saving
        $(".settings-buttons .button").hide();
        $(".settings-buttons .loading-icon").show();
    });


    /**
     * Handle the click on "Upload new file".
     */
    $("#upload-list__new-file").click(function(e) {
        e.preventDefault();

        // Create a new, hidden file picker
        new_file_input = $('<input type="file" name="newfile" style="display:none;">');

        // As soon as a file is picked ...
        new_file_input.change(function(e) {
            settingsChanged();
            
            file_name = e.target.files[0].name;
            file_size = e.target.files[0].size;

            // Ask the backend for the HTML representation of a file
            $.ajax({
                url: "/ajax/get_uploaded_file_html/",
                method: "GET",
                data: {filename: file_name, filesize: file_size},
                success: function(data) {

                    // Create an element from the returned HTML
                    new_file_label = $(data);

                    // Setup the same handlers as is done for the other files
                    new_file_label.find(".upload-list__file__delete-button")
                                  .click(deleteButtonClick);

                    // Add an extra class indicating that this is a new file
                    new_file_label.addClass("to-be-uploaded");

                    // Add it to the list of files (which is part of the form)
                    new_file_label.append(new_file_input);
                    $("#upload-list__new-file").before(new_file_label);
                }
            });
        });

        // Click on that new file picker
        new_file_input.click();
    });


    /**
     * Select a file for later deletion (on saving the settings)
     */
    $(".upload-list__file__delete-button").click(deleteButtonClick);
    function deleteButtonClick(e) {
        e.preventDefault();
        settingsChanged();

        var root = $(this).parents(".upload-list__file");        

        // If it's not yet uploaded we can simply delete 
        // the visual representation and stop here
        if (root.hasClass("to-be-uploaded")) {
            root.remove();
            return;
        }

        root.toggleClass('to-be-deleted');
        checkbox = $(this).find(".deletion-checkbox");

        // Toggle the hidden checkbox
        // and swap the label icon
        var icon = root.find(".upload-list__file__icon i");
        if (checkbox.is(':checked')) {
            checkbox.attr('checked', false);
            $(this).find(".label-delete").show();
            $(this).find(".label-undo").hide();
            
            icon.replaceWith('<i class="far fa-file"></i>');
        } else {
            checkbox.attr('checked', true);
            $(this).find(".label-delete").hide();
            $(this).find(".label-undo").show();

            icon.replaceWith('<i class="fas fa-file-excel"></i>');
        }
    }


    /**
     * To be called when any setting changes.
     * This activates the 'save' and 'cancel' buttons.
     * (Which are by default deactivated)
     */
    function settingsChanged() {
        $(".settings-buttons .button-disabled").removeClass("button-disabled");
    }

});