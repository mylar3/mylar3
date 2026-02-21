# Mylar3 API Reference

Mylar3 exposes a JSON API for programmatic access to your comic library, search, download management, and system administration.

## Overview

### Base URL

```
http://<host>:<port>[/<http_root>]/api
```

All requests use query-string parameters. There is no request body.

### Authentication

Every request (except `getAPI`) requires an `apikey` parameter. Mylar recognizes three key types:

| Key Type | Source | Scope |
|----------|--------|-------|
| **API Key** | Settings > Web Interface | Full access to all commands |
| **Download API Key** | Auto-generated at runtime (`DOWNLOAD_APIKEY`) | File download operations only |
| **SSE Key** | Auto-generated at runtime (`SSE_KEY`) | `checkGlobalMessages` (Server-Sent Events) only |

All API keys are 32-character hex strings.

To retrieve your API key programmatically, use the [`getAPI`](#getapi) endpoint with HTTP credentials.

### Request Format

```
GET /api?apikey=<key>&cmd=<command>[&param1=value1&param2=value2...]
```

### Response Envelope

**Success:**

```json
{
  "success": true,
  "data": { ... }
}
```

**Failure:**

```json
{
  "success": false,
  "error": {
    "code": 460,
    "message": "Description of the error"
  }
}
```

### JSONP Support

Add a `callback` parameter to any request to receive a JSONP response:

```
GET /api?apikey=<key>&cmd=getIndex&callback=myFunction
```

Response:

```javascript
myFunction({"success": true, "data": [...]});
```

### Error Codes

| Code | Meaning |
|------|---------|
| `460` | General API error (missing parameter, invalid key, unknown command, etc.) |

---

## Endpoints

### 1. Authentication

#### getAPI

Retrieve your API key by providing your Mylar HTTP credentials. This is the only command that does not require an `apikey` parameter.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `username` | string | Yes | Mylar HTTP username |
| `password` | string | Yes | Mylar HTTP password |

**Example Request:**

```bash
curl "http://localhost:8090/api?cmd=getAPI&username=admin&password=secret"
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "apikey": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
  }
}
```

---

### 2. Library

#### getIndex

Fetch all comics in your library (watchlist), sorted alphabetically.

**Parameters:** None

**Response Fields:**

| Name | Type | Description |
|------|------|-------------|
| `id` | string | ComicVine ComicID |
| `name` | string | Comic series name |
| `imageURL` | string | Cover image URL |
| `status` | string | Series status (`Active`, `Paused`, `Ended`) |
| `publisher` | string | Publisher name |
| `publishYear` | string | Publication date range (e.g. `"2011 - 2014"`) |
| `year` | string | Series start year |
| `latestIssue` | string | Latest issue number |
| `totalIssues` | integer | Total number of issues |
| `detailsURL` | string | ComicVine detail page URL |
| `alternateSearch` | string | Alternate search terms |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getIndex"
```

**Example Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "40968",
      "name": "Saga",
      "imageURL": "https://comicvine.gamespot.com/a/uploads/.../saga.jpg",
      "status": "Active",
      "publisher": "Image Comics",
      "publishYear": "2012 - Present",
      "year": "2012",
      "latestIssue": "66",
      "totalIssues": 66,
      "detailsURL": "https://comicvine.gamespot.com/saga/...",
      "alternateSearch": null
    }
  ]
}
```

---

#### getComic

Fetch detailed info for a single comic series, including all issues and annuals.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | ComicVine ComicID |

**Response Fields:**

The response `data` object contains three arrays:

**`comic`** (array of 1 object) — same fields as [`getIndex`](#getindex).

**`issues`** (array) — sorted by issue number descending:

| Name | Type | Description |
|------|------|-------------|
| `id` | string | IssueID |
| `name` | string | Issue name/title |
| `imageURL` | string | Issue cover image URL |
| `number` | string | Issue number |
| `releaseDate` | string | Store release date (`YYYY-MM-DD`) |
| `issueDate` | string | Cover date (`YYYY-MM-DD`) |
| `status` | string | Issue status (`Wanted`, `Downloaded`, `Snatched`, `Skipped`, `Archived`) |
| `comicName` | string | Parent comic series name |

**`annuals`** (array) — only populated if annuals integration is enabled:

| Name | Type | Description |
|------|------|-------------|
| `id` | string | IssueID |
| `name` | string | Annual name/title |
| `number` | string | Issue number |
| `releaseDate` | string | Store release date (`YYYY-MM-DD`) |
| `issueDate` | string | Cover date (`YYYY-MM-DD`) |
| `status` | string | Issue status |
| `comicName` | string | Parent comic series name |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getComic&id=40968"
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "comic": [
      {
        "id": "40968",
        "name": "Saga",
        "imageURL": "https://...",
        "status": "Active",
        "publisher": "Image Comics",
        "publishYear": "2012 - Present",
        "year": "2012",
        "latestIssue": "66",
        "totalIssues": 66,
        "detailsURL": "https://...",
        "alternateSearch": null
      }
    ],
    "issues": [
      {
        "id": "987654",
        "name": "Chapter Sixty-Six",
        "imageURL": "https://...",
        "number": "66",
        "releaseDate": "2024-06-26",
        "issueDate": "2024-06-26",
        "status": "Downloaded",
        "comicName": "Saga"
      }
    ],
    "annuals": []
  }
}
```

---

#### getComicInfo

Fetch metadata for a single comic series (without issues).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | ComicVine ComicID |

**Response Fields:** Same as [`getIndex`](#getindex) — returns a single-element array.

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getComicInfo&id=40968"
```

**Example Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "40968",
      "name": "Saga",
      "imageURL": "https://...",
      "status": "Active",
      "publisher": "Image Comics",
      "publishYear": "2012 - Present",
      "year": "2012",
      "latestIssue": "66",
      "totalIssues": 66,
      "detailsURL": "https://...",
      "alternateSearch": null
    }
  ]
}
```

---

#### getIssueInfo

Fetch metadata for a single issue.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | IssueID |

**Response Fields:** Same as the `issues` array in [`getComic`](#getcomic) — returns a single-element array.

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getIssueInfo&id=987654"
```

**Example Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "987654",
      "name": "Chapter Sixty-Six",
      "imageURL": "https://...",
      "number": "66",
      "releaseDate": "2024-06-26",
      "issueDate": "2024-06-26",
      "status": "Downloaded",
      "comicName": "Saga"
    }
  ]
}
```

---

#### getReadList

Fetch all issues on the reading list, sorted by issue date ascending.

**Parameters:** None

**Response Fields:**

| Name | Type | Description |
|------|------|-------------|
| `id` | string | IssueID |
| `number` | string | Issue number |
| `issueDate` | string | Cover date (`YYYY-MM-DD`) |
| `status` | string | Issue status |
| `comicName` | string | Comic series name |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getReadList"
```

**Example Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "123456",
      "number": "1",
      "issueDate": "2024-01-10",
      "status": "Downloaded",
      "comicName": "Saga"
    }
  ]
}
```

---

#### listAnnualSeries

List annuals integrated into existing series, with options for grouping and filtering.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `list_issues` | string | At least one of `list_issues` or `group_series` required | Set to any value to include individual issues |
| `group_series` | string | At least one of `list_issues` or `group_series` required | Set to any value to group results by parent ComicID |
| `show_downloaded` | string | No | Set to any value to show only downloaded annuals |

**Response Fields (per annual):**

| Name | Type | Description |
|------|------|-------------|
| `series` | string | Parent series name |
| `annualname` | string | Annual release name |
| `annualcomicid` | string | Annual's own ComicID |
| `issueid` | integer | IssueID |
| `filename` | string | File location on disk |
| `issuenumber` | string | Issue number |
| `comicid` | integer | Parent ComicID (only when `group_series` is not set) |

When `group_series` is set, the response is an object keyed by ComicID, with arrays of annuals as values. Otherwise, it is a flat array.

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=listAnnualSeries&list_issues=true&group_series=true"
```

**Example Response (grouped):**

```json
{
  "success": true,
  "data": {
    "40968": [
      {
        "series": "Saga",
        "annualname": "Saga Annual 2023",
        "annualcomicid": "150001",
        "issueid": 555123,
        "filename": "Saga Annual 001 (2023).cbz",
        "issuenumber": "1"
      }
    ]
  }
}
```

---

### 3. Search

#### findComic

Search for comics on ComicVine by name. Results are sorted by year and issue count (descending).

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `name` | string | Yes | — | Comic name to search for |
| `issue` | string | No | `null` | Narrow search to a specific issue number |
| `type_` | string | No | `"comic"` | Search type: `comic` or `story_arc` |
| `mode` | string | No | `"series"` | Search mode: `series`, `pullseries`, or `want` |

**Response Fields:**

Results are returned directly as a sorted array (not wrapped in the standard `data` envelope). Fields come from the ComicVine search results and typically include:

| Name | Type | Description |
|------|------|-------------|
| `name` | string | Series name |
| `comicid` | string | ComicVine ComicID |
| `comicyear` | string | Start year |
| `issues` | string | Issue count |
| `publisher` | string | Publisher |
| `comicimage` | string | Cover image URL |
| `url` | string | ComicVine URL |
| `deck` | string | Short description |
| `description` | string | Full description |
| `haveit` | string | Whether series is already in library |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=findComic&name=Saga"
```

---

### 4. Management

#### addComic

Add a comic series to your library by ComicVine ID. The series is queued for adding in a background thread.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | ComicVine ComicID |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=addComic&id=40968"
```

**Example Response:**

```json
{
  "success": true,
  "data": "Successfully queued up addding id: 40968"
}
```

---

#### delComic

Delete a comic series from your library. Optionally delete downloaded files.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `id` | string | Yes | — | ComicVine ComicID (with or without `4050-` prefix) |
| `directory` | string | No | `"false"` | Set to `"true"` to also delete the series folder on disk |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=delComic&id=40968&directory=false"
```

**Example Response:**

```json
{
  "success": true,
  "data": "Successfully deleted Saga (2012) [40968]"
}
```

---

#### pauseComic

Pause monitoring for a comic series (sets status to `Paused`).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | ComicVine ComicID |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=pauseComic&id=40968"
```

**Example Response:** No explicit response body (returns `null`).

---

#### resumeComic

Resume monitoring for a paused comic series (sets status to `Active`).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | ComicVine ComicID |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=resumeComic&id=40968"
```

**Example Response:** No explicit response body (returns `null`).

---

#### refreshComic

Refresh metadata from ComicVine for one or more series. Accepts a single ComicID or a comma-separated list. Runs in a background thread.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | ComicVine ComicID (or comma-separated list, with or without `4050-` prefix) |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=refreshComic&id=40968"
```

**Example Response:**

```json
{
  "success": true,
  "data": "Refresh successfully submitted 40968."
}
```

---

#### recheckFiles

Re-scan downloaded files for one or more series. Accepts a single ComicID or a list.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string or array | Yes | ComicVine ComicID (or JSON array of IDs) |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=recheckFiles&id=40968"
```

---

#### changeBookType

Change the book type classification for a series.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | ComicVine ComicID |
| `booktype` | string | Yes | Target book type. Allowed values: `Print`, `Digital`, `TPB`, `GN`, `HC`, `One-Shot` (case-insensitive) |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=changeBookType&id=40968&booktype=TPB"
```

**Example Response:**

```json
{
  "success": true,
  "data": "[40968] Updated Booktype to TPB."
}
```

---

#### changeStatus

Bulk-change issue statuses across one or more series.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status_from` | string | Yes | Current status to match (e.g. `Skipped`, `Wanted`) |
| `status_to` | string | Yes | New status to set |
| `id` | string or array | Yes | ComicVine ComicID, `"All"` for all series, or a JSON array of IDs |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=changeStatus&status_from=Skipped&status_to=Wanted&id=40968"
```

**Example Response:**

```json
{
  "success": true,
  "data": "..."
}
```

---

### 5. Issues

#### queueIssue

Mark an issue as `Wanted` and immediately trigger a search for it.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | IssueID |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=queueIssue&id=987654"
```

**Example Response:** No explicit response body (returns `null`). The issue status is set to `Wanted` and a search is launched.

---

#### unqueueIssue

Mark an issue as `Skipped` (remove it from the wanted list).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | IssueID |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=unqueueIssue&id=987654"
```

**Example Response:** No explicit response body (returns `null`).

---

#### getUpcoming

Fetch this week's upcoming issues from the weekly pull list that match series in your library.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `include_downloaded_issues` | string | No | `"N"` | Set to `"Y"` to include issues with status `Snatched` or `Downloaded` in addition to `Wanted` |

**Response Fields:**

Returns a flat array (not wrapped in `success`/`data` envelope):

| Name | Type | Description |
|------|------|-------------|
| `ComicName` | string | Comic name from weekly pull list |
| `IssueNumber` | string | Issue number |
| `ComicID` | string | ComicVine ComicID |
| `IssueID` | string | IssueID |
| `IssueDate` | string | Ship date |
| `Status` | string | Issue status (`Wanted`, `Snatched`, `Downloaded`) |
| `DisplayComicName` | string | Display name from your library |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getUpcoming"
```

**Example Response:**

```json
[
  {
    "ComicName": "Saga",
    "IssueNumber": "67",
    "ComicID": "40968",
    "IssueID": "999001",
    "IssueDate": "2024-07-03",
    "Status": "Wanted",
    "DisplayComicName": "Saga"
  }
]
```

---

#### getWanted

Fetch all issues across your library with status `Wanted`. Includes main issues, story arcs (optional), and annuals.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `story_arcs` | string | No | `"false"` | Set to `"true"` to include wanted story arc issues (requires `UPCOMING_STORYARCS` config enabled) |

**Response Fields:**

Returns an object (not wrapped in `success`/`data` envelope) with the following keys:

**`issues`** (array):

| Name | Type | Description |
|------|------|-------------|
| `ComicName` | string | Series name |
| `ComicYear` | string | Series start year |
| `ComicVersion` | string | Volume info |
| `BookType` | string | Book type (`Print`, `TPB`, etc.) |
| `ComicPublisher` | string | Publisher |
| `publisherImprint` | string | Publisher imprint |
| `Issue_Number` | string | Issue number |
| `IssueName` | string | Issue title |
| `ReleaseDate` | string | Store release date |
| `IssueDate` | string | Cover date |
| `DigitalDate` | string | Digital release date |
| `Status` | string | `Wanted` |
| `ComicID` | string | ComicVine ComicID |
| `IssueID` | string | IssueID |
| `DateAdded` | string | Date issue was added to watchlist |

**`story_arcs`** (array, only if requested):

| Name | Type | Description |
|------|------|-------------|
| `Storyarc` | string | Story arc name |
| `StoryArcID` | string | Story arc ID |
| `IssueArcID` | string | Issue arc ID |
| `ComicName` | string | Series name |
| `IssueNumber` | string | Issue number |
| `IssueName` | string | Issue title |
| `ReleaseDate` | string | Store release date |
| `IssueDate` | string | Cover date |
| `DigitalDate` | string | Digital release date |
| `Status` | string | `Wanted` |
| `ComicID` | string | ComicVine ComicID |
| `IssueID` | string | IssueID |
| `DateAdded` | string | Date added |

**`annuals`** (array, only if annuals integration is enabled):

| Name | Type | Description |
|------|------|-------------|
| `ComicName` | string | Annual release name |
| `ComicYear` | string | Series start year |
| `ComicVersion` | string | Volume info |
| `BookType` | string | Book type |
| `ComicPublisher` | string | Publisher |
| `publisherImprint` | string | Publisher imprint |
| `SeriesName` | string | Parent series name |
| `Issue_Number` | string | Issue number |
| `IssueName` | string | Issue title |
| `ReleaseDate` | string | Store release date |
| `IssueDate` | string | Cover date |
| `DigitalDate` | string | Digital release date |
| `Status` | string | `Wanted` |
| `ComicID` | string | Annual ComicID |
| `IssueID` | string | IssueID |
| `SeriesComicID` | string | Parent series ComicID |
| `DateAdded` | string | Date added |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getWanted&story_arcs=true"
```

---

#### getHistory

Fetch the snatch/download history, sorted by date descending.

**Parameters:** None

**Response Fields:**

Returns all columns from the `snatched` table:

| Name | Type | Description |
|------|------|-------------|
| `IssueID` | string | IssueID |
| `ComicName` | string | Series name |
| `Issue_Number` | string | Issue number |
| `Size` | integer | File size in bytes |
| `DateAdded` | string | Date/time the snatch occurred |
| `Status` | string | Snatch status (`Snatched`, `Post-Processed`, `Downloaded`, `Failed`) |
| `FolderName` | string | Download folder name |
| `ComicID` | string | ComicVine ComicID |
| `Provider` | string | Provider used (e.g. indexer name) |
| `Hash` | string | NZB/torrent hash |
| `crc` | string | CRC checksum |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getHistory"
```

**Example Response:**

```json
{
  "success": true,
  "data": [
    {
      "IssueID": "987654",
      "ComicName": "Saga",
      "Issue_Number": "66",
      "Size": 52428800,
      "DateAdded": "2024-06-27 10:30:00",
      "Status": "Post-Processed",
      "FolderName": "Saga.066.2024",
      "ComicID": "40968",
      "Provider": "MyIndexer",
      "Hash": null,
      "crc": null
    }
  ]
}
```

---

### 6. Downloads

#### downloadIssue

Download a comic issue file directly to your browser. Returns the binary file as a download attachment (not JSON).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | IssueID |

**Example Request:**

```bash
curl -O -J "http://localhost:8090/api?apikey=YOUR_KEY&cmd=downloadIssue&id=987654"
```

**Response:** Binary file download (CBZ/CBR/PDF). Returns a failure JSON response if the issue is not downloaded or the file is not found.

---

#### downloadNZB

Download a cached NZB file. Returns the binary file as a download attachment (not JSON).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `nzbname` | string | Yes | NZB filename (must exist in cache directory) |

**Example Request:**

```bash
curl -O -J "http://localhost:8090/api?apikey=YOUR_KEY&cmd=downloadNZB&nzbname=my_comic.nzb"
```

**Response:** Binary NZB file download. Returns a failure JSON response if the file does not exist.

---

#### forceProcess

Trigger post-processing of a downloaded file. Queues the request for asynchronous processing.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `nzb_name` | string | Yes | — | Name of the NZB/download (use `"Manual Run"` for manual processing) |
| `nzb_folder` | string | Yes | — | Path to the download folder |
| `failed` | string | No | `"false"` | Set to `"true"` if this is a failed download |
| `issueid` | string | No | `null` | Specific IssueID to process |
| `comicid` | string | No | `null` | Specific ComicID to process |
| `ddl` | string | No | — | Set to any value to mark as a direct download |
| `oneoff` | string | No | `"False"` | Set to `"True"` for one-off downloads |
| `apc_version` | string | No | — | ComicRN API version (triggers legacy ComicRN processing mode) |
| `comicrn_version` | string | No | — | ComicRN version (required when `apc_version` is set) |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=forceProcess&nzb_name=Saga.066.2024&nzb_folder=/downloads/complete/comics"
```

**Example Response:**

```
Successfully submitted request for post-processing for Saga.066.2024
```

---

#### forceSearch

Force an immediate search for all wanted issues. Runs synchronously and may take a while to complete.

**Parameters:** None

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=forceSearch"
```

**Example Response:** No explicit response body (returns `null`).

---

### 7. Story Arcs

#### getStoryArc

List all story arcs, or get details of a specific arc.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | No | StoryArcID — if provided, returns issues in that arc |
| `customOnly` | string | No | Set to any truthy value to return only custom (user-created) arcs |

**Without `id`** — returns a summary of all arcs:

| Name | Type | Description |
|------|------|-------------|
| `StoryArcID` | string | Story arc ID (custom arcs start with `C`) |
| `StoryArc` | string | Arc name |
| `HighestOrder` | integer | Highest reading order number |

**With `id`** — returns issues in the specified arc, sorted by reading order:

| Name | Type | Description |
|------|------|-------------|
| `StoryArc` | string | Arc name |
| `ReadingOrder` | integer | Position in reading order |
| `ComicID` | string | ComicVine ComicID |
| `ComicName` | string | Series name |
| `IssueNumber` | string | Issue number |
| `IssueID` | string | IssueID |
| `IssueDate` | string | Cover date |
| `IssueName` | string | Issue title |
| `IssuePublisher` | string | Publisher |

**Example Request:**

```bash
# List all story arcs
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getStoryArc"

# Get issues in a specific arc
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getStoryArc&id=56789"

# List custom arcs only
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getStoryArc&customOnly=1"
```

**Example Response (arc list):**

```json
[
  {
    "StoryArcID": "56789",
    "StoryArc": "The Sinestro Corps War",
    "HighestOrder": 12
  }
]
```

> **Note:** `getStoryArc` returns data directly — not wrapped in the standard `success`/`data` envelope.

---

#### addStoryArc

Add issues to an existing story arc, or create a new custom arc.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | No | Existing StoryArcID to append to. If omitted, a new custom arc is created. |
| `storyarcname` | string | Conditional | Name for the new arc (required when `id` is not provided) |
| `issues` | string | Conditional | Comma-separated list of ComicVine IssueIDs (at least one of `issues` or `arclist` required) |
| `arclist` | string | Conditional | Pipe-separated list of `issueID,readingOrder` pairs (at least one of `issues` or `arclist` required) |

**Example Request:**

```bash
# Create a new custom arc
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=addStoryArc&storyarcname=My%20Custom%20Arc&issues=111111,222222,333333"

# Add issues to an existing arc
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=addStoryArc&id=56789&issues=444444,555555"
```

**Example Response:**

```json
{
  "success": true,
  "data": "Adding 3 issue(s) to My Custom Arc"
}
```

---

### 8. Providers

#### listProviders

List all configured Newznab and Torznab search providers.

**Parameters:** None

**Response Fields:**

The response `data` object contains two arrays:

**`newznabs`** (array):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | Provider name |
| `host` | string | Provider URL |
| `apikey` | string | Provider API key |
| `categories` | string | Comma-separated category list (or `null`) |
| `uid` | string | User ID for RSS access |
| `enabled` | boolean | Whether the provider is active |
| `id` | integer | Internal provider ID |

**`torznabs`** (array):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | Provider name |
| `host` | string | Provider URL |
| `apikey` | string | Provider API key |
| `categories` | string | Category string |
| `enabled` | boolean | Whether the provider is active |
| `id` | integer | Internal provider ID |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=listProviders"
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "newznabs": [
      {
        "name": "NZBgeek",
        "host": "https://api.nzbgeek.info",
        "apikey": "abc123...",
        "categories": "7030",
        "uid": "12345",
        "enabled": true,
        "id": 1
      }
    ],
    "torznabs": []
  }
}
```

---

#### addProvider

Add a new Newznab or Torznab search provider.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `providertype` | string | Yes | `"newznab"` or `"torznab"` |
| `name` | string | Yes | Provider display name |
| `host` | string | Yes | Provider URL (must start with `http://` or `https://`) |
| `prov_apikey` | string | Yes | Provider API key |
| `enabled` | string | Yes | Set to any value to enable (omit or set empty to disable) |
| `uid` | string | No | User ID (newznab only, required for RSS) |
| `categories` | string | No | Comma-separated category IDs |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=addProvider&providertype=newznab&name=NZBgeek&host=https://api.nzbgeek.info&prov_apikey=abc123&enabled=true&uid=12345&categories=7030"
```

**Example Response:**

```json
{
  "success": true,
  "data": "Successfully added newznab provider NZBgeek to the provider list [prov_id: 1]"
}
```

---

#### changeProvider

Modify settings for an existing provider. Only the fields you include will be changed.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `providertype` | string | Yes | `"newznab"` or `"torznab"` |
| `name` | string | Conditional | Current provider name (required if `prov_id` not given) |
| `prov_id` | integer | Conditional | Provider ID (required if `name` not given) |
| `altername` | string | No | New name to rename the provider to |
| `host` | string | No | New provider URL |
| `prov_apikey` | string | No | New API key |
| `enabled` | string | No | `"true"` or `"false"` |
| `disabled` | string | No | `"true"` or `"false"` (inverse of `enabled`) |
| `uid` | string | No | New user ID (newznab only) |
| `categories` | string | No | New comma-separated category IDs |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=changeProvider&providertype=newznab&prov_id=1&enabled=false"
```

**Example Response:**

```json
{
  "success": true,
  "data": "Successfully changed ['enabled'] for newznab provider NZBgeek [prov_id:1]"
}
```

---

#### delProvider

Delete a configured search provider.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `providertype` | string | Yes | `"newznab"` or `"torznab"` |
| `name` | string | Conditional | Provider name (required if `prov_id` not given) |
| `prov_id` | integer | Conditional | Provider ID (required if `name` not given) |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=delProvider&providertype=newznab&prov_id=1"
```

**Example Response:**

```json
{
  "success": true,
  "data": "Successfully removed newznab provider NZBgeek [prov_id:1]"
}
```

---

### 9. Media

#### getArt

Retrieve the cover image for a comic series. Returns a JPEG image (not JSON).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | ComicVine ComicID |

**Example Request:**

```bash
curl -o cover.jpg "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getArt&id=40968"
```

**Response:** Binary JPEG image. Returns a failure JSON response if no image is found.

---

#### regenerateCovers

Regenerate cover images for one or more series. Runs in a background thread.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | Yes | One of: a ComicID, a comma-separated list of ComicIDs, `"all"` (all series), or `"missing"` (only series without cached covers) |

**Example Request:**

```bash
# Regenerate covers for all series missing a cached image
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=regenerateCovers&id=missing"

# Regenerate covers for specific series
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=regenerateCovers&id=40968,50123"
```

**Example Response:**

```json
{
  "success": true,
  "data": "RegenerateCovers successfully submitted for 12 series."
}
```

---

#### refreshSeriesjson

Regenerate `series.json` metadata files for one or more series. Runs in a background thread.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `comicid` | string | Yes | One of: a ComicID, a comma-separated list of ComicIDs, `"all"`, `"missing"` (series without `series.json`), or `"refresh-missing"` (re-download missing and refresh) |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=refreshSeriesjson&comicid=missing"
```

---

#### seriesjsonListing

List series and their `series.json` status.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `missing` | string | No | Set to any value to only list series missing their `series.json` file |

**Response Fields:**

| Name | Type | Description |
|------|------|-------------|
| `ComicID` | string | ComicVine ComicID |
| `ComicLocation` | string | Path to the series folder on disk |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=seriesjsonListing&missing=true"
```

**Example Response:**

```json
{
  "success": true,
  "data": [
    {
      "ComicID": "40968",
      "ComicLocation": "/comics/Saga (2012)"
    }
  ]
}
```

---

### 10. Health

#### getHealth

Return all active health check results with a summary and the last run timestamp.

**Parameters:** None

**Response Fields:**

| Name | Type | Description |
|------|------|-------------|
| `results` | array | Array of health check result objects |
| `summary` | object | Issue counts by severity |
| `last_run` | string | ISO 8601 timestamp of last health check run (or `null`) |

**Each result object:**

| Name | Type | Description |
|------|------|-------------|
| `id` | integer | Database row ID |
| `check_type` | string | Category: `infrastructure`, `provider`, `download`, `task`, `config`, or `detected` |
| `check_name` | string | Specific check identifier (e.g. `root_folder`, `comicvine_api`, `disk_space`) |
| `severity` | string | `error`, `warning`, or `notice` |
| `message` | string | Human-readable description of the issue |
| `wiki_url` | string | Link to the relevant wiki troubleshooting page |
| `source` | string | How the finding was generated: `health_check` or `log_intercept` |
| `metadata` | object | Check-specific details (e.g. `{"path": "/comics", "free_gb": 0.5}`) |
| `first_seen` | string | ISO 8601 timestamp when the issue was first detected |
| `last_seen` | string | ISO 8601 timestamp when the issue was last confirmed |
| `check_count` | integer | Number of consecutive check cycles this issue has persisted |
| `resolved_at` | string | ISO 8601 timestamp if resolved (or `null`) |

**Summary object:**

| Name | Type | Description |
|------|------|-------------|
| `errors` | integer | Count of error-severity issues |
| `warnings` | integer | Count of warning-severity issues |
| `notices` | integer | Count of notice-severity issues |
| `total` | integer | Total active issues |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getHealth"
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "id": 1,
        "check_type": "infrastructure",
        "check_name": "disk_space",
        "severity": "warning",
        "message": "Low disk space on /comics \u2014 3.2 GB free (warning threshold: 5.0 GB).",
        "wiki_url": "https://github.com/mylar3/mylar3/wiki/Health-Checks#disk-space",
        "source": "health_check",
        "metadata": {"path": "/comics", "free_gb": 3.2, "total_gb": 500.0},
        "first_seen": "2024-06-27T10:00:00+00:00",
        "last_seen": "2024-06-27T10:15:00+00:00",
        "check_count": 3,
        "resolved_at": null
      }
    ],
    "summary": {
      "errors": 0,
      "warnings": 1,
      "notices": 0,
      "total": 1
    },
    "last_run": "2024-06-27T10:15:00+00:00"
  }
}
```

---

#### getHealthSummary

Return only the health check summary counts (lighter weight than `getHealth`).

**Parameters:** None

**Response Fields:**

| Name | Type | Description |
|------|------|-------------|
| `summary` | object | Same summary object as [`getHealth`](#gethealth) |
| `last_run` | string | ISO 8601 timestamp of last health check run (or `null`) |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getHealthSummary"
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "summary": {
      "errors": 0,
      "warnings": 1,
      "notices": 0,
      "total": 1
    },
    "last_run": "2024-06-27T10:15:00+00:00"
  }
}
```

---

### 11. System

#### getVersion

Return version and installation information.

**Parameters:** None

**Response Fields:**

| Name | Type | Description |
|------|------|-------------|
| `git_path` | string | Path to the git executable |
| `install_type` | string | Installation method (`git`, `exe`, `docker`, etc.) |
| `current_version` | string | Currently running commit hash |
| `latest_version` | string | Latest available commit hash |
| `commits_behind` | integer | Number of commits behind the latest version |

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getVersion"
```

**Example Response:**

```json
{
  "success": true,
  "data": {
    "git_path": "/usr/bin/git",
    "install_type": "git",
    "current_version": "abc1234def5678",
    "latest_version": "def5678abc1234",
    "commits_behind": 3
  }
}
```

---

#### checkGithub

Check GitHub for a newer version of Mylar3, then return the updated version info (same as `getVersion`).

**Parameters:** None

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=checkGithub"
```

**Example Response:** Same format as [`getVersion`](#getversion).

---

#### getLogs

Fetch the in-memory log buffer.

**Parameters:** None

**Response:** Returns the raw log list array (not wrapped in `success`/`data` envelope).

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=getLogs"
```

---

#### clearLogs

Clear the in-memory log buffer.

**Parameters:** None

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=clearLogs"
```

**Example Response:**

```
Cleared log
```

---

#### shutdown

Shut down the Mylar3 application.

**Parameters:** None

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=shutdown"
```

**Example Response:** No response body (the server is shutting down).

---

#### restart

Restart the Mylar3 application.

**Parameters:** None

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=restart"
```

**Example Response:** No response body (the server is restarting).

---

#### update

Update Mylar3 to the latest version and restart. Check `install_type` via `getVersion` first — may not work for all installation methods.

**Parameters:** None

**Example Request:**

```bash
curl "http://localhost:8090/api?apikey=YOUR_KEY&cmd=update"
```

**Example Response:** No response body (the server is updating and restarting).

---

### 12. Real-Time

#### checkGlobalMessages

Server-Sent Events (SSE) endpoint for real-time browser notifications. Requires the SSE API key.

Returns `text/event-stream` responses with named events.

**Parameters:** None (but requires `apikey` to be the SSE key)

**Event Types:**

| Event | Description |
|-------|-------------|
| `addbyid` | Progress updates when adding a comic by ID |
| `scheduler_message` | Scheduler status updates |
| `config_check` | Configuration check notifications |
| `shutdown` | Server shutdown notification |
| `health_update` | Health check results pushed in real-time |
| `check_update` | Version update availability notification |

**Example Request:**

```bash
curl -N "http://localhost:8090/api?apikey=SSE_KEY&cmd=checkGlobalMessages"
```

**Example Response (SSE stream):**

```
event: health_update
data: {"errors": [], "warnings": [], "error_count": 0, "warning_count": 0, "notice_count": 0}

event: addbyid
data: {
data: "status": "success",
data: "comicid": "40968",
data: "message": "Successfully added Saga",
data: "tables": "comic",
data: "comicname": "Saga",
data: "seriesyear": "2012"
data: }
```

---

## Command Reference (Quick List)

| # | Command | Category | Description |
|---|---------|----------|-------------|
| 1 | `getAPI` | Auth | Retrieve API key using HTTP credentials |
| 2 | `getIndex` | Library | List all comics in watchlist |
| 3 | `getComic` | Library | Get comic details with issues and annuals |
| 4 | `getComicInfo` | Library | Get comic metadata (no issues) |
| 5 | `getIssueInfo` | Library | Get single issue metadata |
| 6 | `getReadList` | Library | List reading list issues |
| 7 | `listAnnualSeries` | Library | List integrated annual series |
| 8 | `findComic` | Search | Search ComicVine for comics |
| 9 | `addComic` | Management | Add comic to library |
| 10 | `delComic` | Management | Delete comic from library |
| 11 | `pauseComic` | Management | Pause comic monitoring |
| 12 | `resumeComic` | Management | Resume comic monitoring |
| 13 | `refreshComic` | Management | Refresh metadata from ComicVine |
| 14 | `recheckFiles` | Management | Re-scan files for a series |
| 15 | `changeBookType` | Management | Change series book type |
| 16 | `changeStatus` | Management | Bulk-change issue statuses |
| 17 | `queueIssue` | Issues | Mark issue as wanted and search |
| 18 | `unqueueIssue` | Issues | Mark issue as skipped |
| 19 | `getUpcoming` | Issues | This week's pull list matches |
| 20 | `getWanted` | Issues | All wanted issues |
| 21 | `getHistory` | Issues | Snatch/download history |
| 22 | `downloadIssue` | Downloads | Download a comic file |
| 23 | `downloadNZB` | Downloads | Download a cached NZB file |
| 24 | `forceProcess` | Downloads | Trigger post-processing |
| 25 | `forceSearch` | Downloads | Search for all wanted issues |
| 26 | `getStoryArc` | Story Arcs | List or view story arcs |
| 27 | `addStoryArc` | Story Arcs | Create or add to story arcs |
| 28 | `listProviders` | Providers | List search providers |
| 29 | `addProvider` | Providers | Add a search provider |
| 30 | `changeProvider` | Providers | Modify a search provider |
| 31 | `delProvider` | Providers | Delete a search provider |
| 32 | `getArt` | Media | Get series cover image |
| 33 | `regenerateCovers` | Media | Regenerate cover images |
| 34 | `refreshSeriesjson` | Media | Regenerate series.json files |
| 35 | `seriesjsonListing` | Media | List series.json status |
| 36 | `getHealth` | Health | Full health check results |
| 37 | `getHealthSummary` | Health | Health check summary counts |
| 38 | `getVersion` | System | Version information |
| 39 | `checkGithub` | System | Check for updates |
| 40 | `getLogs` | System | Fetch log buffer |
| 41 | `clearLogs` | System | Clear log buffer |
| 42 | `shutdown` | System | Shut down Mylar |
| 43 | `restart` | System | Restart Mylar |
| 44 | `update` | System | Update and restart Mylar |
| 45 | `checkGlobalMessages` | Real-Time | SSE event stream |
