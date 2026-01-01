# Veterans Verify - Page Selectors Documentation

> Based on Chrome DevTools MCP Exploration, 2025-12-25

## Start Debug Browser

```bash
# Run Script
E:\veterans-verify\scripts\start-chrome-devtools.bat

# Or Manual Start
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\.cache\veterans-chrome-mcp\user-data" --no-first-run
```

---

## Flow Overview

```
1. Veterans Claim Page → Click "Log in"
2. Login/Register Page → Enter Email → Click "Continue"
3. Create Password Page → Enter Password → Click "Continue"
4. Email Verify Page → Enter Code → Click "Continue"
5. Confirm Age Page → Enter Name + DOB → Click "Continue"
6. Veterans Page (Logged In) → Click "Verify eligibility"
7. SheerID Verify Form → Fill Veteran Info → Submit
8. SheerID Email Verify → Click Verify Link
9. Verify Success → Get 1 Year Plus
```

---

## Page 1: Veterans Claim Page

**URL**: `https://chatgpt.com/veterans-claim`

| Element | CSS Selector Suggestion | Description |
|---------|-------------------------|-------------|
| Login Button | `button:has-text("Log in")` | Primary CTA |
| Learn More | `button:has-text("Learn more")` | Secondary |

**Page Check**:
- Title contains "One year of ChatGPT Plus free"
- URL contains `/veterans-claim`

---

## Page 2: Login or Register

**URL**: `https://auth.openai.com/log-in-or-create-account`

| Element | CSS Selector | Playwright Selector |
|---------|--------------|---------------------|
| Email Input | `input[name="email"]` | `textbox "Email address"` |
| Continue Button | `button[type="submit"]` | `button "Continue"` |
| Google Login | - | `button:has-text("Google")` |
| Apple Login | - | `button:has-text("Apple")` |
| Microsoft Login | - | `button:has-text("Microsoft")` |
| Phone Login | - | `button:has-text("Phone")` |

**Page Check**:
- URL contains `log-in-or-create-account`
- Title "Log in or Sign up"

---

## Page 3: Create Password (New User)

**URL**: `https://auth.openai.com/create-account/password`

| Element | CSS Selector | Playwright Selector |
|---------|--------------|---------------------|
| Email Readonly | `input[readonly]` | `textbox "Email address"` (readonly) |
| Edit Email | `a:has-text("Edit")` | `link "Edit email"` |
| Password Input | `input[type="password"]` | `textbox "Password"` |
| Show Password | - | `button "Show password"` |
| Continue Button | `button[type="submit"]` | `button "Continue"` |

**Password Req**: At least 12 chars

**Page Check**:
- URL contains `create-account/password`
- Title "Create password"

---

## Page 4: Email Verification

**URL**: `https://auth.openai.com/email-verification`

| Element | CSS Selector | Playwright Selector |
|---------|--------------|---------------------|
| Code Input | `input[name="code"]` | `textbox "Code"` |
| Continue Button | `button[type="submit"]` | `button "Continue"` |
| Resend Email | - | `button "Resend email"` |

**Code Format**: 6 digits/chars mixed

**Sender**: OpenAI / ChatGPT

**Page Check**:
- URL contains `email-verification`
- Title "Check your email"

---

## Page 5: Confirm Age (New Page!)

**URL**: `https://auth.openai.com/about-you`

| Element | CSS Selector | Playwright Selector |
|---------|--------------|---------------------|
| Full Name Input | `input[name="name"]` | `textbox "Full name"` |
| Year | `input[type="number"]` | `spinbutton "Year"` |
| Month | `input[type="number"]` | `spinbutton "Month"` |
| Day | `input[type="number"]` | `spinbutton "Day"` |
| Continue Button | `button[type="submit"]` | `button "Continue"` |

**Page Check**:
- URL contains `about-you`
- Title "Tell us about you"

---

## Page 6: Veterans Page (Logged In)

**URL**: `https://chatgpt.com/veterans-claim?redirectedFromAuth=true`

| Element | CSS Selector | Playwright Selector |
|---------|--------------|---------------------|
| Verify Button | `button:has-text("Verify")` | `button "Verify eligibility"` |

**Page Check**:
- Button text changed from "Log in" to "Verify eligibility"

---

## Page 7: SheerID Verify Form (Core!)

**URL**: `https://services.sheerid.com/verify/690415d58971e73ca187d8c9/?verificationId=...`

**Page Title**: "Unlock this Military-Only Offer"

### Status Field

| Option | Description |
|--------|-------------|
| Active Duty | Active Duty |
| Military Veteran or Retiree | Veteran/Retiree |
| Reservist or National Guard | Reservist/National Guard |

**Selector**: `combobox "Status"`

### Branch of service Field

| Option | BIRLS Data |
|--------|------------|
| Air Force | Air Force |
| Army | Army |
| Coast Guard | Coast Guard |
| Marine Corps | Marine Corps |
| Navy | Navy |
| Space Force | Space Force |

**Selector**: `combobox "Branch of service"`

### Full Form Fields

| Field | Type | Playwright Selector | Note |
|-------|------|---------------------|------|
| Status | Dropdown | `combobox "Status"` | |
| Branch of service | Dropdown | `combobox "Branch of service"` | |
| First name | Text | `textbox "First name"` | |
| Last name | Text | `textbox "Last name"` | |
| Date of birth - Month | Dropdown | `combobox "Date of birth..."` | |
| Date of birth - Day | Text | `textbox "Day"` (1st) | |
| Date of birth - Year | Text | `textbox "Year"` (1st) | |
| Discharge date - Month | Dropdown | `combobox "Discharge date..."` | |
| Discharge date - Day | Text | `textbox "Day"` (2nd) | |
| Discharge date - Year | Text | `textbox "Year"` (2nd) | |
| Email address | Text | `textbox "Email address..."` | |
| Submit Button | Button | `button "Verify My Eligibility"` | Initially disabled |

### Key Constraints

- **Discharge date MUST be within past 12 months!**
- Submit button enables only after all required fields are filled
- Email must be valid (will receive link)

---

## Page 8: Verification Result

> ⚠️ To be completed

**Success**: Redirect to `chatgpt.com`, account shows Plus

**Failure Scenes**:
- "Invalid discharge date" - > 12 months
- "Already verified" - Info used
- "Unable to verify" - Cannot verify info
- "We couldn't verify your status" - Need doc upload

---

## Error Handling

| Error Type | Page Feature | Action |
|------------|--------------|--------|
| Email Registered | Redirect to login | Use existing or change email |
| Password Weak | Red prompt | Increase complexity |
| Code Error | Error prompt | Retry code |
| Code Expired | Resend click | Resend email |
| Rate limit | Limit prompt | Wait and retry |

---

## Camoufox Automation Example

```python
async def fill_login_form(page, email: str):
    """Fill Login Form"""
    # Wait for email input
    email_input = page.locator('input[type="email"]')
    await email_input.fill(email)

    # Click Continue
    continue_btn = page.locator('button:has-text("Continue")')
    await continue_btn.click()
```

---

## Update Log

- 2025-12-25: Initial version, login/register flow (Page 1-4)
- 2025-12-25: Added Confirm Age Page (Page 5)
- 2025-12-25: Added Logged-in Veterans Page (Page 6)
- 2025-12-25: **Full SheerID Form Selectors (Page 7)**
- TODO: Add Result Page (Page 8)
