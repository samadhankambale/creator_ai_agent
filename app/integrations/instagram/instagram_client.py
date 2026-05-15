import time
import requests


# ======================================================
# CREATE MEDIA CONTAINER
# ======================================================

def create_media_container(
    image_url,
    caption,
    access_token,
    instagram_user_id
):

    try:

        print("===================================")
        print("CREATE MEDIA CONTAINER")
        print("===================================")

        print("IMAGE URL:")
        print(image_url)

        print("INSTAGRAM USER ID:")
        print(instagram_user_id)

        print("ACCESS TOKEN:")
        print(access_token)

        url = (
            f"https://graph.facebook.com/v20.0/"
            f"{instagram_user_id}/media"
        )

        payload = {

            "image_url":
            image_url,

            "caption":
            caption[:2200],

            "access_token":
            access_token
        }

        response = requests.post(

            url,

            data=payload
        )

        print("STATUS CODE:")
        print(response.status_code)

        data = response.json()

        print("INSTAGRAM CREATE RESPONSE:")
        print(data)

        # ------------------------------------------
        # SUCCESS
        # ------------------------------------------

        if "id" in data:

            return {

                "success": True,

                "creation_id":
                data["id"],

                "response":
                data
            }

        # ------------------------------------------
        # FAILURE
        # ------------------------------------------

        return {

            "success": False,

            "response":
            data
        }

    except Exception as e:

        print("CREATE MEDIA ERROR:")
        print(str(e))

        return {

            "success": False,

            "error": str(e)
        }


# ======================================================
# PUBLISH MEDIA
# ======================================================

def publish_media(
    creation_id,
    access_token,
    instagram_user_id
):

    try:

        print("===================================")
        print("PUBLISH MEDIA")
        print("===================================")

        print("CREATION ID:")
        print(creation_id)

        url = (
            f"https://graph.facebook.com/v20.0/"
            f"{instagram_user_id}/media_publish"
        )

        payload = {

            "creation_id":
            creation_id,

            "access_token":
            access_token
        }

        response = requests.post(

            url,

            data=payload
        )

        print("PUBLISH STATUS:")
        print(response.status_code)

        data = response.json()

        print("PUBLISH RESPONSE:")
        print(data)

        # ------------------------------------------
        # SUCCESS
        # ------------------------------------------

        if "id" in data:

            return {

                "success": True,

                "response":
                data
            }

        # ------------------------------------------
        # FAILURE
        # ------------------------------------------

        return {

            "success": False,

            "response":
            data
        }

    except Exception as e:

        print("PUBLISH ERROR:")
        print(str(e))

        return {

            "success": False,

            "error": str(e)
        }


# ======================================================
# MAIN INSTAGRAM POST
# ======================================================

def post_to_instagram(
    image_url,
    caption,
    access_token,
    instagram_user_id
):

    try:

        print("===================================")
        print("START INSTAGRAM POST")
        print("===================================")

        # ------------------------------------------
        # CREATE CONTAINER
        # ------------------------------------------

        container = create_media_container(

            image_url=image_url,

            caption=caption,

            access_token=access_token,

            instagram_user_id=
            instagram_user_id
        )

        print("CONTAINER RESULT:")
        print(container)

        if not container["success"]:

            return {

                "success": False,

                "response":
                container
            }

        creation_id = (
            container["creation_id"]
        )

        # ------------------------------------------
        # WAIT FOR META PROCESSING
        # ------------------------------------------

        print("WAITING FOR META PROCESSING")

        time.sleep(5)

        # ------------------------------------------
        # PUBLISH MEDIA
        # ------------------------------------------

        publish_result = publish_media(

            creation_id=creation_id,

            access_token=access_token,

            instagram_user_id=
            instagram_user_id
        )

        print("FINAL PUBLISH RESULT:")
        print(publish_result)

        if not publish_result["success"]:

            return {

                "success": False,

                "response":
                publish_result
            }

        print("===================================")
        print("INSTAGRAM POST SUCCESS")
        print("===================================")

        return {

            "success": True,

            "platform":
            "instagram",

            "response":
            publish_result
        }

    except Exception as e:

        print("INSTAGRAM POST ERROR:")
        print(str(e))

        return {

            "success": False,

            "error": str(e)
        }