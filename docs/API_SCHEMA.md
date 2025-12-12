# Meetnet Vlaamse Banken API Schema Documentation

> **Source**: https://api.meetnetvlaamsebanken.be/V2-help/
>
> **JSON Schemas**: See `docs/schemas/` for official JSON schema files

Base URL: `https://api.meetnetvlaamsebanken.be`

## Key Types (from Commons.json)

| Type | Pattern | Example | Description |
|------|---------|---------|-------------|
| LocationKey | `^[0-9A-Z]{3}$` | `NPT` | 3 alphanumeric chars identifying a location |
| ParameterKey | `^[0-9A-Z]{3}$` | `WVC` | 3 alphanumeric chars identifying a parameter |
| LocationParameterKey | `^[0-9A-Z]{6}$` | `NPTWVC` | 6 chars = LocationKey + ParameterKey |
| ParameterTypeKey | integer | `1` | Parameter type identifier |

## MessageModelList (Multi-language strings)

Names and descriptions are arrays of localized messages, NOT plain strings:

```json
[
  {"Culture": "nl", "Message": "Windsnelheid"},
  {"Culture": "en", "Message": "Wind speed"},
  {"Culture": "fr", "Message": "Vitesse du vent"}
]
```

---

## Authentication

### POST /Token

Schema: `TokenModel.json`

**Request** (x-www-form-urlencoded):

| Field | Value |
|-------|-------|
| grant_type | `password` (only supported value) |
| username | Email or username |
| password | User password |

**Response**:

```json
{
  "access_token": "string",
  "token_type": "Bearer",
  "expires_in": 3600,
  ".expires": "string|null",
  ".issued": "string|null",
  "userName": "string|null"
}
```

Required fields: `access_token`, `expires_in`, `token_type`

**Usage**: Include in subsequent requests as `Authorization: Bearer {access_token}`

---

## GET /V2/catalog

Schema: `CatalogModel.json`

Returns complete catalog with locations, parameters, and available data combinations.

**Response Structure**:

```json
{
  "Customer": {
    "FullName": "string",
    "Login": "email@example.com"
  },
  "Locations": [
    {
      "ID": "NPT",
      "Name": [{"Culture": "nl", "Message": "Nieuwpoort"}],
      "Description": [{"Culture": "nl", "Message": "..."}],
      "PositionWKT": "POINT (2.123 51.456)"
    }
  ],
  "Parameters": [
    {
      "ID": "WVC",
      "Name": [{"Culture": "nl", "Message": "Windsnelheid"}],
      "Unit": "m/s",
      "ParameterTypeID": 1,
      "MaxValue": null,
      "MinValue": null
    }
  ],
  "ParameterTypes": {
    "1": {
      "ID": 1,
      "SortOrder": 1,
      "Name": [{"Culture": "nl", "Message": "Wind"}]
    }
  },
  "AvailableData": [
    {
      "ID": "NPTWVC",
      "Location": "NPT",
      "Parameter": "WVC",
      "CurrentInterval": 10,
      "Publications": ["string"]
    }
  ],
  "ProjectionWKT": "GEOGCS[...]"
}
```

**Required fields per model**:

- LocationModel: `ID`, `Name`, `PositionWKT`
- ParameterModel: `ID`, `Name`, `Unit`, `ParameterTypeID`
- LocationParameterModel: `ID`, `Location`, `Parameter`, `CurrentInterval`, `Publications`

---

## GET /V2/currentData

Schemas: `CurrentData_Request.json`, `CurrentDataModel.json`

Returns latest values for all or filtered data points.

**Request** (optional query parameter):

- `IDs`: Array of LocationParameterKeys to filter

**⚠️ IMPORTANT: Response is an ARRAY directly** (not wrapped in an object):

```json
[
  {
    "ID": "NPTWVC",
    "Timestamp": "2024-01-15T12:00:00Z",
    "Value": 5.2
  },
  {
    "ID": "NPTWRS",
    "Timestamp": "2024-01-15T12:00:00Z",
    "Value": 180.5
  }
]
```

**Required fields**: `ID`, `Timestamp`, `Value`

Note: `Value` can be `null` if no data is available.

---

## POST /V2/getData

Schemas: `GetData_Request.json`, `GetDataModel.json`

Returns historical data for specified date range.

**Request body**:

```json
{
  "StartTime": "2024-01-01T00:00:00Z",
  "EndTime": "2024-01-02T00:00:00Z",
  "IDs": ["NPTWVC", "NPTWRS"]
}
```

**Required fields**: `StartTime`, `EndTime`, `IDs`

**Response**:

```json
{
  "StartTime": "2024-01-01T00:00:00Z",
  "EndTime": "2024-01-02T00:00:00Z",
  "Intervals": [10],
  "Values": [
    {
      "ID": "NPTWVC",
      "StartTime": "2024-01-01T00:00:00Z",
      "EndTime": "2024-01-02T00:00:00Z",
      "MinValue": 2.1,
      "MaxValue": 12.5,
      "Values": [
        {"Timestamp": "2024-01-01T00:10:00Z", "Value": 5.2},
        {"Timestamp": "2024-01-01T00:20:00Z", "Value": 5.8}
      ]
    }
  ]
}
```

---

## Data Formats

Specify format via Accept header:

- `Accept: application/json` (recommended - faster, less bandwidth)
- `Accept: application/xml`
