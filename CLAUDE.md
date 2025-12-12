# Instructions

* Base yourself on API docs - see `docs/API_SCHEMA.md` for full schema details
* This is a Home Assistant custom integration for the Meetnet Vlaamse Banken API
* API uses MessageModelList for multi-language fields (Name, Description) - use `extract_message()` to get string values
* Key types: LocationKey (3 chars), ParameterKey (3 chars), LocationParameterKey (6 chars = Location + Parameter)
