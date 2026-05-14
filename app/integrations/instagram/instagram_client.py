import httpx


async def post_to_instagram(
    image_url,
    caption,
    access_token,
    instagram_user_id
):

    # ==================================================
    # INSTAGRAM CAPTION LIMIT
    # ==================================================

    short_caption = caption[:2000]

    print("SHORT CAPTION:")
    print(short_caption)

    print("IMAGE URL:")
    print(image_url)

    print("INSTAGRAM USER ID:")
    print(instagram_user_id)

    async with httpx.AsyncClient(
        timeout=60.0
    ) as client:

        # ==============================================
        # CREATE MEDIA CONTAINER
        # ==============================================

        create_url = (
            "https://graph.facebook.com/v20.0/"
            f"{instagram_user_id}/media"
        )

        create_payload = {

            "image_url":
            image_url,

            "caption":
            short_caption,

            "access_token":
            access_token
        }

        print("CREATE PAYLOAD:")
        print(create_payload)

        response = await client.post(

            create_url,

            data=create_payload
        )

        data = response.json()

        print("CREATE RESPONSE:")
        print(data)

        # ==============================================
        # HANDLE CREATE ERROR
        # ==============================================

        if "id" not in data:

            raise Exception(data)

        creation_id = data["id"]

        print("CREATION ID:")
        print(creation_id)

        # ==============================================
        # PUBLISH POST
        # ==============================================

        publish_url = (
            "https://graph.facebook.com/v20.0/"
            f"{instagram_user_id}"
            "/media_publish"
        )

        publish_payload = {

            "creation_id":
            creation_id,

            "access_token":
            access_token
        }

        print("PUBLISH PAYLOAD:")
        print(publish_payload)

        publish_response = await client.post(

            publish_url,

            data=publish_payload
        )

        publish_data = (
            publish_response.json()
        )

        print("PUBLISH RESPONSE:")
        print(publish_data)

        return publish_data