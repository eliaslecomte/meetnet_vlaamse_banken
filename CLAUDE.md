# Instructions

* Base yourself on API docs:
  - `docs/API_SCHEMA.md` - Human-readable documentation
  - `docs/schemas/*.json` - Official JSON schemas from the API
* This is a Home Assistant custom integration for the Meetnet Vlaamse Banken API

## Key API Notes

* API uses MessageModelList for multi-language fields (Name, Description) - use `extract_message()` to get string values
* Key types: LocationKey (3 chars), ParameterKey (3 chars), LocationParameterKey (6 chars = Location + Parameter)
* **GET /V2/currentData returns an ARRAY directly**, not `{"Values": [...]}`
* AvailableData uses field names `Location` and `Parameter`, not `LocationID`/`ParameterID`
