function get(url, success_function) {
    return $.ajax({
        url: url,
        type: "GET",
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        success: function(result, status, xhr)
        {
            console.log(xhr)
            success_function(result,status,xhr)
        },
        error: function(xhr, status, error)
        {
            $("#output-text").text(`error : ${status} - ${error}`);
            alert(`error : ${status} - ${error}`)
        },
        timeout: 120 * 1000
    })
}

function post(url, data, success_function) {
    return $.ajax({
        url: url,
        type: "POST",
        data: data,
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        success: function(result, status, xhr)
        {
            console.log(xhr)
            success_function(result,status,xhr)
        },
        error: function(xhr, status, error)
        {
            $("#output-text").text(`error : ${status} - ${error}`);
            alert(`error : ${status} - ${error}`)
        },
        timeout: 120 * 1000
    })
}

base_api_url = `http://127.0.0.1:8000/mohaverekhan/api`
words_url = `${base_api_url}/words`
word_normals_url = `${base_api_url}/word-normals`

texts_url = `${base_api_url}/texts`
text_normals_url = `${base_api_url}/text-normals`
text_tags_url = `${base_api_url}/text-tags`

tag_sets_url = `${base_api_url}/tag-sets`
tags_url = `${base_api_url}/tags`

validators_url = `${base_api_url}/validators`
normalizers_url = `${base_api_url}/normalizers`
taggers_url = `${base_api_url}/taggers`

selected_normalizer = "no-normalizer"
selected_tagger = "no-tagger"
text_id = "no-id"
input_text = "no-text"
output_text = "no-text"

function do_after_success_getting_normalizers(result, status, xhr) {
    for ( var i in xhr.responseJSON) {
        normalizer = xhr.responseJSON[i]
        console.log(normalizer.name)
        console.log(normalizer.show_name)
        $( "#normalizers" ).append($("<option></option>")
                .attr("value", normalizer.name)
                .text(normalizer.show_name)); 
    }
    $('.selectpicker').selectpicker('refresh');
}

function do_after_success_getting_taggers(result, status, xhr) {
    for ( var i in xhr.responseJSON) {
        tagger = xhr.responseJSON[i]
        console.log(tagger.name)
        console.log(tagger.show_name)
        $( "#taggers" ).append($("<option></option>")
                .attr("value", tagger.name)
                .text(tagger.show_name)); 
        
    }
    $('.selectpicker').selectpicker('refresh');
}


get(`${normalizers_url}?is_automatic=true`, do_after_success_getting_normalizers)
get(`${taggers_url}?is_automatic=true`, do_after_success_getting_taggers)

$(document).ready(function(){

    var csrftoken = Cookies.get('csrftoken');
    function csrfSafeMethod(method) {
        // these HTTPs methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });

    function do_after_success_tagging_text(result, status, xhr) {
        tagged_tokens_html = xhr.responseJSON.tagged_tokens_html
        console.log(tagged_tokens_html)
        $("#output-text").html(tagged_tokens_html);
    }
    function do_after_success_normalizing_text(result, status, xhr) {
        text_id = xhr.responseJSON.id
        console.log(`text_id (normal) : ${text_id}`)
        $("#output-text").html(xhr.responseJSON.content.replace(/\n/g, "<br>"))
    }
    function normal_after_success_getting_item(result, status, xhr) {
        var text = xhr.responseJSON
        text_id = text.id
        console.log(`text_id : ${text_id}`)
        console.log(`text content : ${text}`)
        get(`${normalizers_url}/${selected_normalizer}/normalize?text-id=${text_id}`, do_after_success_normalizing_text)
    }

    function tag_after_success_getting_item(result, status, xhr) {
        var text = xhr.responseJSON
        text_id = text.id
        console.log(`text_id : ${text_id}`)
        console.log(`text content : ${text}`)
        get(`${taggers_url}/${selected_tagger}/tag?text-id=${text_id}`, do_after_success_tagging_text)
    }

    $("#normal-button").click(function() {
        input_text = $("#input-text").val()
        console.log(`input_text : ${input_text}`)

        selected_normalizer = $("#normalizers").children("option:selected").val();
        console.log(`selected_normalizer : ${selected_normalizer}`)

        if ( selected_normalizer == "no-normalizer") {
            $("#output-text").text('لطفا یک نرمال‌کننده انتخاب کنید.');
            return
        }

        input_text = input_text.replace(/\n/g, "\\n")
        console.log(`input_text : \n${input_text}\n`)

        var data = `{"content": "${input_text}"}`
        console.log(`data : ${data}`)

        post(texts_url, data, normal_after_success_getting_item)
    })

    $("#tag-button").click(function() {
        input_text = $("#input-text").val()
        console.log(`input_text : ${input_text}`)

        selected_tagger = $("#taggers").children("option:selected").val();
        console.log(`selected_tagger : ${selected_tagger}`)

        if (selected_tagger == "no-tagger") {
            $("#output-text").text('لطفا یک برچسب‌زننده انتخاب کنید.');
            return
        }

        input_text = input_text.replace(/\n/g, "\\n")
        console.log(`input_text : \n${input_text}\n`)

        var data = `{"content": "${input_text}"}`
        console.log(`data : ${data}`)

        post(texts_url, data, tag_after_success_getting_item)
    })

});

