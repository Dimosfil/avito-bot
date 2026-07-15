[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "CheckAccess",
        "GetProfile",
        "InitializeProfile",
        "SetProfile",
        "GetCategoryTree",
        "GetCategoryFields",
        "GetItems",
        "StartUpload",
        "GetCurrentUpload",
        "WatchCurrentUpload"
    )]
    [string]$Action,

    [string]$FeedUrl,
    [string]$FeedName = "Avito regional feed",
    [string]$ReportEmail,
    [ValidateSet("Enabled", "Disabled")]
    [string]$AutoloadState = "Disabled",
    [ValidateRange(1, 100000)]
    [int]$Rate = 1,
    [ValidateRange(0, 23)]
    [int]$TimeSlot = ([TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, "Russian Standard Time").Hour),
    [string]$NodeSlug,
    [ValidateSet("active", "old", "blocked", "rejected", "removed")]
    [string]$ItemStatus = "active",
    [ValidateRange(2, 60)]
    [int]$PollSeconds = 5,
    [ValidateRange(1, 120)]
    [int]$MaxPolls = 24,
    [switch]$ConfirmChange,
    [switch]$ConfirmPublish
)

$ErrorActionPreference = "Stop"
$ApiBase = "https://api.avito.ru"

function Get-RequiredEnvironmentValue {
    param([string]$Name)

    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "$Name is required in the process or user environment. Never pass API secrets as command-line arguments."
    }
    return $value
}

function Convert-ResponseContentFromUtf8 {
    param([Microsoft.PowerShell.Commands.HtmlWebResponseObject]$Response)

    return [System.Text.Encoding]::UTF8.GetString(
        [System.Text.Encoding]::GetEncoding(28591).GetBytes($Response.Content)
    )
}

function Get-AvitoAccessToken {
    $clientId = Get-RequiredEnvironmentValue -Name "AVITO_CLIENT_ID"
    $clientSecret = Get-RequiredEnvironmentValue -Name "AVITO_CLIENT_SECRET"
    $response = Invoke-RestMethod `
        -Method Post `
        -Uri "$ApiBase/token" `
        -ContentType "application/x-www-form-urlencoded" `
        -Body @{
            grant_type = "client_credentials"
            client_id = $clientId
            client_secret = $clientSecret
        }

    if ([string]::IsNullOrWhiteSpace($response.access_token)) {
        throw "Avito did not return an access token."
    }
    return $response.access_token
}

function Invoke-AvitoJson {
    param(
        [string]$Method,
        [string]$Path,
        [string]$Token,
        [object]$Body = $null
    )

    $parameters = @{
        Method = $Method
        Uri = "$ApiBase$Path"
        Headers = @{ Authorization = "Bearer $Token" }
    }
    if ($null -ne $Body) {
        $json = $Body | ConvertTo-Json -Depth 12
        $parameters.ContentType = "application/json; charset=utf-8"
        $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes($json)
    }

    try {
        $response = Invoke-WebRequest @parameters
        if ([string]::IsNullOrWhiteSpace($response.Content)) {
            return $null
        }
        return (Convert-ResponseContentFromUtf8 -Response $response) | ConvertFrom-Json
    }
    catch {
        $status = $null
        $message = $null
        if ($null -ne $_.Exception.Response) {
            $status = $_.Exception.Response.StatusCode.value__
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
                $content = $reader.ReadToEnd()
                $reader.Dispose()
                if (-not [string]::IsNullOrWhiteSpace($content)) {
                    $errorBody = $content | ConvertFrom-Json
                    if ($null -ne $errorBody.error) {
                        $message = $errorBody.error.message
                    }
                    elseif ($null -ne $errorBody.message) {
                        $message = $errorBody.message
                    }
                }
            }
            catch {
                $message = $null
            }
        }
        throw "Avito API request failed: $Method $Path; HTTP $status; $message"
    }
}

function Get-Account {
    param([string]$Token)
    return Invoke-AvitoJson -Method "GET" -Path "/core/v1/accounts/self" -Token $Token
}

function Assert-ChangeConfirmed {
    if (-not $ConfirmChange) {
        throw "This action changes the Avito Autoload profile. Repeat with -ConfirmChange."
    }
}

if ($Action -in @("InitializeProfile", "SetProfile") -and -not $ConfirmChange) {
    throw "This action changes the Avito Autoload profile. Repeat with -ConfirmChange."
}
if ($Action -eq "StartUpload" -and -not $ConfirmPublish) {
    throw "StartUpload can publish listings and consume package placements. Repeat with -ConfirmPublish."
}

$token = Get-AvitoAccessToken

switch ($Action) {
    "CheckAccess" {
        $account = Get-Account -Token $token
        $profileStatus = 200
        try {
            $profile = Invoke-AvitoJson -Method "GET" -Path "/autoload/v2/profile" -Token $token
        }
        catch {
            $profile = $null
            $profileStatus = if ($_.Exception.Message -match 'HTTP ([0-9]+)') { [int]$Matches[1] } else { 0 }
        }
        [pscustomobject]@{
            authorized = $true
            account_id = $account.id
            autoload_profile_http_status = $profileStatus
            autoload_enabled = if ($null -ne $profile) { $profile.autoload_enabled } else { $null }
        } | ConvertTo-Json
    }
    "GetProfile" {
        Invoke-AvitoJson -Method "GET" -Path "/autoload/v2/profile" -Token $token | ConvertTo-Json -Depth 10
    }
    "InitializeProfile" {
        Assert-ChangeConfirmed
        $account = Get-Account -Token $token
        $email = if (-not [string]::IsNullOrWhiteSpace($ReportEmail)) { $ReportEmail } else { $account.email }
        if ([string]::IsNullOrWhiteSpace($email)) {
            throw "ReportEmail is required because the Avito account did not return an email."
        }
        $body = @{
            agreement = $true
            autoload_enabled = $false
            feeds_data = @()
            report_email = $email
            schedule = @()
        }
        Invoke-AvitoJson -Method "POST" -Path "/autoload/v2/profile" -Token $token -Body $body | Out-Null
        [pscustomobject]@{ initialized = $true; autoload_enabled = $false } | ConvertTo-Json
    }
    "SetProfile" {
        Assert-ChangeConfirmed
        if ($FeedUrl -notmatch '^https://') {
            throw "FeedUrl must be a public HTTPS URL."
        }
        $account = Get-Account -Token $token
        $email = if (-not [string]::IsNullOrWhiteSpace($ReportEmail)) { $ReportEmail } else { $account.email }
        if ([string]::IsNullOrWhiteSpace($email)) {
            throw "ReportEmail is required because the Avito account did not return an email."
        }
        $body = @{
            autoload_enabled = ($AutoloadState -eq "Enabled")
            feeds_data = @(@{ feed_name = $FeedName; feed_url = $FeedUrl })
            report_email = $email
            schedule = @(@{
                rate = $Rate
                weekdays = @(0, 1, 2, 3, 4, 5, 6)
                time_slots = @($TimeSlot)
            })
        }
        Invoke-AvitoJson -Method "POST" -Path "/autoload/v2/profile" -Token $token -Body $body | Out-Null
        [pscustomobject]@{
            configured = $true
            autoload_enabled = $body.autoload_enabled
            feed_url = $FeedUrl
            rate = $Rate
            time_slot_moscow = $TimeSlot
        } | ConvertTo-Json
    }
    "GetCategoryTree" {
        Invoke-AvitoJson -Method "GET" -Path "/autoload/v1/user-docs/tree" -Token $token | ConvertTo-Json -Depth 30
    }
    "GetCategoryFields" {
        if ([string]::IsNullOrWhiteSpace($NodeSlug)) {
            throw "NodeSlug is required for GetCategoryFields."
        }
        Invoke-AvitoJson -Method "GET" -Path "/autoload/v1/user-docs/node/$NodeSlug/fields" -Token $token | ConvertTo-Json -Depth 20
    }
    "GetItems" {
        $result = Invoke-AvitoJson -Method "GET" -Path "/core/v1/items?status=$ItemStatus&per_page=100&page=1" -Token $token
        [pscustomobject]@{
            status = $ItemStatus
            count = @($result.resources).Count
            items = @($result.resources | ForEach-Object {
                [pscustomobject]@{
                    id = $_.id
                    status = $_.status
                    title = $_.title
                    price = $_.price
                    address = $_.address
                    url = $_.url
                }
            })
            meta = $result.meta
        } | ConvertTo-Json -Depth 10
    }
    "StartUpload" {
        if (-not $ConfirmPublish) {
            throw "StartUpload can publish listings and consume package placements. Repeat with -ConfirmPublish."
        }
        Invoke-AvitoJson -Method "POST" -Path "/autoload/v1/upload" -Token $token | Out-Null
        [pscustomobject]@{ upload_started = $true } | ConvertTo-Json
    }
    "GetCurrentUpload" {
        $upload = Invoke-AvitoJson -Method "GET" -Path "/autoload/v4/uploads/current" -Token $token
        $items = Invoke-AvitoJson -Method "GET" -Path "/autoload/v4/uploads/current/items" -Token $token
        [pscustomobject]@{ upload = $upload; items = $items } | ConvertTo-Json -Depth 20
    }
    "WatchCurrentUpload" {
        for ($attempt = 1; $attempt -le $MaxPolls; $attempt++) {
            $upload = Invoke-AvitoJson -Method "GET" -Path "/autoload/v4/uploads/current" -Token $token
            $items = Invoke-AvitoJson -Method "GET" -Path "/autoload/v4/uploads/current/items" -Token $token
            $result = [pscustomobject]@{
                attempt = $attempt
                status = $upload.status
                upload_id = $upload.upload_id
                items = $items.items
            }
            $result | ConvertTo-Json -Depth 20

            if ($upload.status -in @("success", "error", "failed")) {
                break
            }
            if ($attempt -lt $MaxPolls) {
                Start-Sleep -Seconds $PollSeconds
            }
        }
    }
}
