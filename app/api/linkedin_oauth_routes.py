from typing import Optional

from fastapi import (
    APIRouter,
    Depends
)

from fastapi.responses import (
    RedirectResponse,
    HTMLResponse
)

from sqlalchemy.orm import Session

from app.database.dependencies import (
    get_db
)

from app.integrations.linkedin.linkedin_client import (
    get_linkedin_auth_url,
    exchange_code_for_token,
    get_linkedin_profile
)

from app.integrations.whatsapp.whatsapp_client import (
    send_message_sync,
    send_buttons_sync
)

from app.services.social_account_service import (
    social_account_service
)


router = APIRouter(
    prefix="/oauth/linkedin",
    tags=["LinkedIn OAuth"]
)


# =====================================================
# CONNECT LINKEDIN
# =====================================================

@router.get("/connect")
async def connect_linkedin(
    whatsapp_number: str
):

    auth_url = (
        get_linkedin_auth_url(
            whatsapp_number
        )
    )

    print("================================")
    print("LINKEDIN AUTH URL")
    print("================================")

    print(auth_url)

    return RedirectResponse(
        url=auth_url
    )


# =====================================================
# CALLBACK
# =====================================================

@router.get("/callback")
async def linkedin_callback(

    code: Optional[str] = None,

    state: Optional[str] = None,

    error: Optional[str] = None,

    error_description: Optional[str] = None,

    db: Session = Depends(get_db)
):

    try:

        print("================================")
        print("LINKEDIN CALLBACK")
        print("================================")

        print("CODE:")
        print(code)

        print("STATE:")
        print(state)

        print("ERROR:")
        print(error)

        print("ERROR DESCRIPTION:")
        print(error_description)

        # =========================================
        # LINKEDIN ERROR
        # =========================================

        if error:

            return HTMLResponse(

                content=f"""
                <html>

                    <body
                        style="
                            font-family: Arial;
                            text-align: center;
                            padding-top: 80px;
                        "
                    >

                        <h2>
                            LinkedIn Authorization Failed
                        </h2>

                        <p>
                            {error}
                        </p>

                        <p>
                            {error_description}
                        </p>

                    </body>

                </html>
                """,

                status_code=400
            )

        # =========================================
        # NO CODE
        # =========================================

        if not code:

            return HTMLResponse(

                content="""
                <html>

                    <body
                        style="
                            font-family: Arial;
                            text-align: center;
                            padding-top: 80px;
                        "
                    >

                        <h2>
                            No authorization code received
                        </h2>

                    </body>

                </html>
                """,

                status_code=400
            )

        # =========================================
        # EXCHANGE TOKEN
        # =========================================

        token_response = (
            exchange_code_for_token(
                code
            )
        )

        print("================================")
        print("TOKEN RESPONSE")
        print("================================")

        print(token_response)

        access_token = (
            token_response.get(
                "access_token"
            )
        )

        if not access_token:

            return HTMLResponse(

                content=f"""
                <html>

                    <body
                        style="
                            font-family: Arial;
                            text-align: center;
                            padding-top: 80px;
                        "
                    >

                        <h2>
                            LinkedIn token exchange failed
                        </h2>

                        <pre>
                        {token_response}
                        </pre>

                    </body>

                </html>
                """,

                status_code=400
            )

        # =========================================
        # GET PROFILE
        # =========================================

        profile = (
            get_linkedin_profile(
                access_token
            )
        )

        print("================================")
        print("LINKEDIN PROFILE")
        print("================================")

        print(profile)

        person_id = (
            profile.get("id")
        )

        username = (
            profile.get(
                "localizedFirstName",
                "LinkedIn"
            )
        )

        print("================================")
        print("LINKEDIN SAVE DEBUG")
        print("================================")

        print("PERSON ID:")
        print(person_id)

        print("USERNAME:")
        print(username)

        # =========================================
        # INVALID PROFILE
        # =========================================

        if not person_id:

            return HTMLResponse(

                content=f"""
                <html>

                    <body
                        style="
                            font-family: Arial;
                            text-align: center;
                            padding-top: 80px;
                        "
                    >

                        <h2>
                            Failed to fetch LinkedIn profile
                        </h2>

                        <pre>
                        {profile}
                        </pre>

                    </body>

                </html>
                """,

                status_code=400
            )

        # =========================================
        # SAVE ACCOUNT
        # =========================================

        social_account_service.connect_platform_account(

            db=db,

            whatsapp_number=
            state,

            platform=
            "linkedin",

            access_token=
            access_token,

            platform_user_id=
            person_id,

            username=
            username
        )

        print("================================")
        print("LINKEDIN CONNECTED SUCCESSFULLY")
        print("================================")

        # =========================================
        # SEND SUCCESS MESSAGE
        # =========================================

        send_message_sync(

            state,

            (
                "✅ LinkedIn connected successfully."
            )
        )

        # =========================================
        # SEND NEW BUTTONS
        # =========================================

        send_buttons_sync(

            state,

            "Choose action",

            [

                {
                    "id":
                    "post_now",

                    "title":
                    "Post Now"
                },

                {
                    "id":
                    "schedule_post",

                    "title":
                    "Schedule"
                }
            ]
        )

        # =========================================
        # SUCCESS PAGE
        # =========================================

        return HTMLResponse(

            content="""
            <html>

                <head>

                    <title>
                        LinkedIn Connected
                    </title>

                </head>

                <body
                    style="
                        font-family: Arial;
                        text-align: center;
                        padding-top: 80px;
                    "
                >

                    <h1>
                        ✅ LinkedIn Connected Successfully
                    </h1>

                    <p>
                        Return to WhatsApp
                        and continue posting.
                    </p>

                </body>

            </html>
            """,

            status_code=200
        )

    except Exception as e:

        print("================================")
        print("LINKEDIN CALLBACK ERROR")
        print("================================")

        print(str(e))

        return HTMLResponse(

            content=f"""
            <html>

                <body
                    style="
                        font-family: Arial;
                        text-align: center;
                        padding-top: 80px;
                    "
                >

                    <h2>
                        LinkedIn connection failed
                    </h2>

                    <pre>
                    {str(e)}
                    </pre>

                </body>

            </html>
            """,

            status_code=500
        )