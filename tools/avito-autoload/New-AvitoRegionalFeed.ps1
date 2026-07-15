[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

function Get-PropertyValue {
    param(
        [object[]]$Sources,
        [string]$Name
    )

    foreach ($source in $Sources) {
        if ($null -eq $source) {
            continue
        }

        $property = $source.PSObject.Properties[$Name]
        if ($null -ne $property -and $null -ne $property.Value) {
            return $property.Value
        }
    }

    return $null
}

function Expand-TemplateValue {
    param(
        [object]$Value,
        [object]$City
    )

    if ($Value -isnot [string]) {
        return $Value
    }

    $cityName = [string](Get-PropertyValue -Sources @($City) -Name "name")
    $citySlug = [string](Get-PropertyValue -Sources @($City) -Name "slug")
    return $Value.Replace("{City}", $cityName).Replace("{CitySlug}", $citySlug)
}

function Assert-TextLength {
    param(
        [string]$Name,
        [string]$Value,
        [int]$Maximum
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name is required."
    }

    if ($Value.Length -gt $Maximum) {
        throw "$Name exceeds the Avito limit of $Maximum characters."
    }
}

function Write-ElementIfPresent {
    param(
        [System.Xml.XmlWriter]$Writer,
        [string]$Name,
        [object]$Value
    )

    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return
    }

    $Writer.WriteElementString($Name, [string]$Value)
}

$manifestFullPath = (Resolve-Path -LiteralPath $ManifestPath).Path
$manifestText = [System.IO.File]::ReadAllText($manifestFullPath, [System.Text.Encoding]::UTF8)
$manifest = $manifestText | ConvertFrom-Json

$defaults = $manifest.defaults
$template = $manifest.template
$ads = @()

if ($null -ne $manifest.ads) {
    $ads = @($manifest.ads | ForEach-Object {
        [pscustomobject]@{ Ad = $_; City = $null; Template = $null }
    })
}
elseif ($null -ne $template -and $null -ne $manifest.cities) {
    $ads = @($manifest.cities | ForEach-Object {
        [pscustomobject]@{ Ad = $_; City = $_; Template = $template }
    })
}

if ($ads.Count -eq 0) {
    throw "Manifest must contain either ads, or template plus cities."
}

$seenIds = @{}
$prepared = @()

foreach ($entry in $ads) {
    $sources = @($entry.Ad, $entry.Template, $defaults)
    $city = $entry.City

    $id = Get-PropertyValue -Sources $sources -Name "id"
    if ([string]::IsNullOrWhiteSpace([string]$id)) {
        $id = Get-PropertyValue -Sources $sources -Name "idPattern"
    }
    $id = [string](Expand-TemplateValue -Value $id -City $city)

    $title = [string](Expand-TemplateValue -Value (Get-PropertyValue -Sources $sources -Name "title") -City $city)
    $description = [string](Expand-TemplateValue -Value (Get-PropertyValue -Sources $sources -Name "description") -City $city)
    $address = [string](Expand-TemplateValue -Value (Get-PropertyValue -Sources $sources -Name "address") -City $city)
    $images = @(Get-PropertyValue -Sources $sources -Name "images")

    Assert-TextLength -Name "Id" -Value $id -Maximum 100
    Assert-TextLength -Name "Title for $id" -Value $title -Maximum 100
    Assert-TextLength -Name "Description for $id" -Value $description -Maximum 7500

    if ($seenIds.ContainsKey($id)) {
        throw "Duplicate ad Id in manifest: $id"
    }
    $seenIds[$id] = $true

    if ($images.Count -eq 0) {
        throw "At least one image URL is required for $id."
    }
    if ($images.Count -gt 10) {
        throw "Avito accepts no more than 10 images for $id."
    }
    foreach ($imageUrl in $images) {
        if ([string]$imageUrl -notmatch '^https?://') {
            throw "Image URL for $id must start with http:// or https://."
        }
    }

    $latitude = Get-PropertyValue -Sources $sources -Name "latitude"
    $longitude = Get-PropertyValue -Sources $sources -Name "longitude"
    if ([string]::IsNullOrWhiteSpace($address) -and ($null -eq $latitude -or $null -eq $longitude)) {
        throw "Address or both latitude and longitude are required for $id."
    }

    $prepared += [pscustomobject]@{
        Id = $id
        Sources = $sources
        Title = $title
        Description = $description
        Address = $address
        Latitude = $latitude
        Longitude = $longitude
        Images = $images
    }
}

$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = [System.IO.Path]::GetDirectoryName($outputFullPath)
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
}

$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.Indent = $true
$settings.NewLineChars = "`n"
$settings.NewLineHandling = [System.Xml.NewLineHandling]::Replace

$writer = [System.Xml.XmlWriter]::Create($outputFullPath, $settings)
try {
    $writer.WriteStartDocument()
    $writer.WriteStartElement("Ads")
    $writer.WriteAttributeString("formatVersion", "3")
    $writer.WriteAttributeString("target", "Avito.ru")

    foreach ($item in $prepared) {
        $writer.WriteStartElement("Ad")
        $writer.WriteElementString("Id", $item.Id)

        $mapping = [ordered]@{
            ListingFee = "listingFee"
            AdStatus = "adStatus"
            ManagerName = "managerName"
            ContactPhone = "contactPhone"
            ContactMethod = "contactMethod"
            Category = "category"
            ServiceType = "serviceType"
            ServiceSubtype = "serviceSubtype"
            ServiceSubspecies = "serviceSubspecies"
        }
        foreach ($xmlName in $mapping.Keys) {
            Write-ElementIfPresent -Writer $writer -Name $xmlName -Value (Get-PropertyValue -Sources $item.Sources -Name $mapping[$xmlName])
        }

        $writer.WriteElementString("Title", $item.Title)
        $writer.WriteStartElement("Description")
        $writer.WriteCData($item.Description)
        $writer.WriteEndElement()

        Write-ElementIfPresent -Writer $writer -Name "Price" -Value (Get-PropertyValue -Sources $item.Sources -Name "price")
        Write-ElementIfPresent -Writer $writer -Name "Address" -Value $item.Address
        Write-ElementIfPresent -Writer $writer -Name "Latitude" -Value $item.Latitude
        Write-ElementIfPresent -Writer $writer -Name "Longitude" -Value $item.Longitude

        $details = [ordered]@{
            Consultations = "consultations"
            WorkWithContract = "workWithContract"
            Prepayment = "prepayment"
            Place = "place"
        }
        foreach ($xmlName in $details.Keys) {
            Write-ElementIfPresent -Writer $writer -Name $xmlName -Value (Get-PropertyValue -Sources $item.Sources -Name $details[$xmlName])
        }

        $additionalFields = Get-PropertyValue -Sources $item.Sources -Name "additionalFields"
        if ($null -ne $additionalFields) {
            foreach ($property in $additionalFields.PSObject.Properties) {
                Write-ElementIfPresent -Writer $writer -Name $property.Name -Value $property.Value
            }
        }

        $writer.WriteStartElement("Images")
        foreach ($imageUrl in $item.Images) {
            $writer.WriteStartElement("Image")
            $writer.WriteAttributeString("url", [string]$imageUrl)
            $writer.WriteEndElement()
        }
        $writer.WriteEndElement()

        $writer.WriteEndElement()
    }

    $writer.WriteEndElement()
    $writer.WriteEndDocument()
}
finally {
    $writer.Dispose()
}

[pscustomobject]@{
    output = $outputFullPath
    ads = $prepared.Count
    ids = @($prepared | ForEach-Object { $_.Id })
} | ConvertTo-Json -Depth 4
