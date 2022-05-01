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

$(document).ready(function () {

    $("#settings-form").change(function (e) {
        settingsChanged();
    });


    let tagsFromDb = $("#tagsFromDb").text();

    $('#textbox_pmid').val(tagsFromDb);

    $('#textbox_pmid').inputTags({
        // tags: tagList,
        max: 50,
        maxLength: 8,
        errors: {
            empty: 'Attention, you cannot add an empty tag.',
            minLength: 'Attention, your tag must have at least %s characters.',
            maxLength: 'Attention, maximum length of a PMID can be %s.',
            max: 'Attention, maximum number of entries is %s.',
            exists: 'Attention, this tag already exists !',
            timeout: 8000
        },
        init: function (elem) {
            console.log('Event called on plugin init', elem);
            if (elem.tags.length == 0) {
                disableTagSaveButton();
            }
        },
        create: function (elem) {
            let tagList = elem.tags;
            let lastItemIndex = tagList.length - 1;
            let lastItem = tagList[lastItemIndex];
            let lastItemAsNumber = Number(lastItem);
            if (isNaN(lastItemAsNumber)) {
                tagList.splice(lastItemIndex, 1);
            }
            console.log('Event called when an item is created', elem);

            let resultList = "";
            tagList.forEach(tag => {
                resultList += '<span class="inputTags-item" data-tag="' + tag + '"><span class="value">' + tag + '</span><i class="close-item">×</i></span>'
            });

            $('.inputTags-list').find('span').remove()
            $('.inputTags-list').append(resultList);

            if (elem.tags.length == 0) {
                disableTagSaveButton();
            }
            else enableTagSaveButton();

        },
        update: function () {
            console.log('Event called when an item is updated');
        },
        destroy: function (elem) {

            console.log(tagsFromDb);
            console.log(elem.tags.length);
            if (elem.tags.length == 0 && tagsFromDb == ''){
                 disableTagSaveButton();
            }
            console.log('Event called when an item is deleted',elem);
        },
        selected: function () {
            console.log('Event called when an item is selected');
        },
        unselected: function () {
            console.log('Event called when an item is unselected');
        },
        change: function (elem) {
            console.log('Event called on item change', elem);

        }
    });

    function disableTagSaveButton() {
        $("#settings-buttons_txtbox_save").addClass("button-disabled");
        $("#settings-buttons_txtbox_save").attr("disabled", "disabled");
    }

    function enableTagSaveButton() {
        $("#settings-buttons_txtbox_save").removeClass("button-disabled");
        $("#settings-buttons_txtbox_save").removeAttr("disabled");
    }

    /**
     * When clicking on the "save" button, hide the buttons
     * and show a loading icon.
     */
    $("#settings-buttons__save").click(function (e) {
        // Do not prevent the default behaviour since this
        // is what submits the form and triggers the saving
        $(".settings-buttons .button").hide();
        $(".settings-buttons .loading-icon").show();
    });


    /**
     * Handle the click on "Upload new file".
     */
    $("#upload-list__new-file").click(function (e) {
        e.preventDefault();

        // Create a new, hidden file picker
        new_file_input = $('<input type="file" name="newfile" style="display:none;">');

        // As soon as a file is picked ...
        new_file_input.change(function (e) {

            file_name = e.target.files[0].name;
            file_size = e.target.files[0].size;

            // Ask the backend for the HTML representation of a file
            $.ajax({
                url: "/ajax/get_uploaded_file_html/",
                method: "GET",
                data: {filename: file_name, filesize: file_size},
                success: function (data) {

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

                    settingsChanged();
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
        var root = $(this).parents(".upload-list__file");

        // If it's not yet uploaded we can simply delete 
        // the visual representation and stop here
        if (root.hasClass("to-be-uploaded")) {
            root.remove();
            settingsChanged();
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

        settingsChanged();
    }


    /**
     * To be called when any setting changes.
     * This activates the 'save' and 'cancel' buttons.
     * (Which are by default deactivated)
     */
    function settingsChanged() {
        // Enable the "Save" and "Cancel" buttons
        $("#settings-buttons__save").removeAttr('disabled');
        $(".settings-buttons .button-disabled").removeClass("button-disabled");

        // Show a help message if the user made any
        // changes in the uploads area
        num_new_files = $(".to-be-uploaded").length;
        num_deleted_files = $(".to-be-deleted").length
        if (num_new_files + num_deleted_files > 0) {
            $(".upload-list__title__help-msg").css("display", "inline");
        } else {
            $(".upload-list__title__help-msg").hide()
        }
    }

});