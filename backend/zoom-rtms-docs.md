# Zoom Realtime Media Streams (RTMS) Documentation

> Source: Zoom RTMS official documentation. This file combines three reference pages: "Stream a single participant's video," "Event reference," and "Data type definitions."

---

## Table of Contents

1. [Stream a single participant's video](#stream-a-single-participants-video)
2. [Event reference](#event-reference)
3. [Data type definitions](#data-type-definitions)

---

## Stream a single participant's video

By default, Realtime Media Streams (RTMS) sends the video data of the active speaker. If your app needs to track a specific participant, you can switch to individual stream mode. In this mode, you choose which participant's video to receive and can change that selection at any time during the meeting.

> **Note:** Only one individual video stream can be active at a time. Subscribing to a new participant automatically unsubscribes from the previous one.

### Prerequisites

Complete the *Working with streams* flow through **Step 3: App establishes signaling connection** before configuring individual video streams.

### Step 1: Configure the media handshake request

When sending the media handshake request, set `data_opt` to `4` (`VIDEO_SINGLE_INDIVIDUAL_STREAM`) in the video media parameters. This tells the RTMS server that your app will manage video subscriptions manually rather than receiving the active speaker automatically.

```json
{
  "msg_type": 3,
  "protocol_version": 1,
  "meeting_uuid": "your_meeting_uuid",
  "rtms_stream_id": "your_rtms_stream_id",
  "signature": "your_signature",
  "media_type": 2,
  "media_params": {
    "video": {
      "codec": 5,
      "resolution": 2,
      "data_opt": 4,
      "fps": 25
    }
  }
}
```

No video data is sent until you subscribe to a participant.

### Step 2: Subscribe to participant video events

Once the stream is active, subscribe to `PARTICIPANT_VIDEO_ON` (event type `8`) and `PARTICIPANT_VIDEO_OFF` (event type `9`) events using the *Subscribe to events* message. These events tell your app which participants have their cameras on and are available to subscribe to.

```json
{
  "msg_type": 18,
  "event_type": [8, 9]
}
```

### Step 3: Receive participant video events

When a participant turns their camera on, the signaling connection sends a participant video on event. Use the `user_id` from this event to send a video subscription request in the next step.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 8,
    "timestamp": 1727384349123,
    "participants": [
      {
        "user_id": 16778240
      }
    ]
  }
}
```

When a participant turns their camera off, the signaling connection sends a participant video off event. If your app is currently subscribed to that participant, no further video data will arrive until you subscribe to a different participant.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 9,
    "timestamp": 1727384349123,
    "participants": [
      {
        "user_id": 16778240
      }
    ]
  }
}
```

### Step 4: Subscribe to a participant's video stream

Send a video subscription request through the signaling connection with the `user_id` of the participant you want to receive video from. Set `subscribe` to `true` to start receiving video from that participant, or `false` to stop.

```json
{
  "msg_type": 28,
  "user_id": 16778240,
  "subscribe": true,
  "timestamp": 1738392033699
}
```

The signaling connection responds with a video subscription response. A `status_code` of `0` means the subscription was successful and video data will begin arriving on the media connection.

```json
{
  "msg_type": 29,
  "user_id": 16778240,
  "status_code": 0,
  "reason": "OK",
  "timestamp": 1738392033699
}
```

### Step 5: Switch to a different participant

To switch the video stream to a different participant, send a new video subscription request with the new participant's `user_id`. You do not need to unsubscribe from the current participant first — the RTMS server handles this automatically when the new subscription request arrives.

```json
{
  "msg_type": 28,
  "user_id": 98765432,
  "subscribe": true,
  "timestamp": 1738392099000
}
```

### Step 6: Unsubscribe from a participant's video stream

To stop receiving video without subscribing to a different participant, send a video subscription request with `subscribe` set to `false`. No video data will be sent until you send a new subscription request.

```json
{
  "msg_type": 28,
  "user_id": 16778240,
  "subscribe": false,
  "timestamp": 1738392099000
}
```

### Handling video gaps

When there is no active individual subscription — such as after a participant turns off their camera or you have explicitly unsubscribed — the RTMS server sends no video data. If your app is recording the meeting for playback, insert filler frames during these gaps when muxing video with audio. Use timestamps from audio packets to determine the duration of each gap. For more information, see *Combining media data*.

---

## Event reference

The Realtime Media Streams (RTMS) events and messages included here outline how your app and RTMS work together to receive session updates, establish signaling and media connections, manage session states, handle keep-alive requests, and receive media data.

The examples on this page use meeting-specific values (such as `meeting_uuid` and `meeting.rtms_started`), but the message structure is the same across all RTMS-supported products.

### Message classification

This table outlines the messages that RTMS currently supports, and their corresponding transmission channels.

| Signaling connection | Media connection |
|---|---|
| SIGNALING_HAND_SHAKE_REQ | KEEP_ALIVE_RESP |
| SIGNALING_HAND_SHAKE_RESP | MEDIA_DATA_AUDIO |
| DATA_HAND_SHAKE_REQ | MEDIA_DATA_VIDEO |
| DATA_HAND_SHAKE_RESP | MEDIA_DATA_SHARE |
| EVENT_SUBSCRIPTION | MEDIA_DATA_TRANSCRIPT |
| EVENT_UPDATE | MEDIA_DATA_CHAT |
| CLIENT_READY_ACK | |
| STREAM_STATE_UPDATE | |
| SESSION_STATE_UPDATE | |
| SESSION_STATE_REQ | |
| SESSION_STATE_RESP | |
| KEEP_ALIVE_REQ | |
| STREAM_STATE_REQ | |
| STREAM_STATE_RESP | |
| STREAM_CLOSE_REQ | |
| STREAM_CLOSE_RESP | |
| VIDEO_SUBSCRIPTION_REQ | |
| VIDEO_SUBSCRIPTION_RESP | |

### Signaling handshake request

*Sent to the signaling connection*

Send a signed handshake request to the `server_urls` provided in the `meeting.rtms_started` event, also known as the signaling connection. Use your app credentials with the session details to generate the signature. For more information, see *App establishes signaling connection*.

Use `meeting.rtms_started` and `meeting.rtms_stopped` events in the Webhook reference to get initial session details like the `meeting_uuid` and `rtms_stream_id`.

```json
{
  "msg_type": 1,
  "protocol_version": 1,
  "sequence": 1,
  "meeting_uuid": "xxxxxxxxxx",
  "rtms_stream_id": "xxxxxxxxxx",
  "signature": "xxxxxxxxxx",
  "buffer_data": false
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The request from the app to the RTMS server to initiate a handshake. See `RTMS_MESSAGE_TYPE`. |
| `protocol_version` | int | The RTMS design version. By default, it's 1.0. |
| `sequence` | int | The sequence number of the message. Must start at 1. |
| `meeting_uuid` | string | The unique identifier for the session. |
| `rtms_stream_id` | string | The unique identifier of the RTMS stream. Multiple streams are possible for a session if streaming access stops or restarts. |
| `signature` | string | The authentication signature created using app credentials and session details. |
| `buffer_data` | bool | Optional. Default is `true`. When set to `false`, any audio data captured between the time the `rtms_started` webhook event is received and the time the signaling connection is established will be dropped. When `buffer_data` is `false`, only the initial buffer data is dropped — audio data continues to be buffered during connection interruptions, and any buffered data is transmitted once a new connection is established. |

### Signaling handshake response

*Sent from the signaling connection*

The signaling connection will respond with a signaling handshake response that includes the URLs of the media connections.

```json
{
  "msg_type": 2,
  "protocol_version": 1,
  "sequence": 0,
  "status_code": 0,
  "reason": "",
  "media_server": {
    "server_urls": {
      "audio": "wss://127.0.0.0:443",
      "video": "wss://127.0.0.0:443",
      "transcript": "wss://127.0.0.0:443",
      "all": "wss://127.0.0.0:443"
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The response from the signaling connection to the app after a handshake attempt. See `RTMS_MESSAGE_TYPE`. |
| `protocol_version` | int | The RTMS design version. By default, it's 1.0. |
| `sequence` | int | The sequence number of the message. |
| `status_code` | int | The status code of the message. Status 0 means success. See `RTMS_STATUS_CODE`. |
| `reason` | string | Empty if successful. If failed, contains the reason for the failure. |
| `media_server` | object | The media connection information. |
| `server_urls` | object | Locations of available media connections. The response depends on the app's available scopes (e.g., if the app only supports audio, only audio will be included). |

### Media handshake request

*Sent to the media connection*

To establish a connection, send a handshake request to the media connection(s) of the RTMS server(s) included in the signaling handshake, along with the associated media parameters. The media connection responds with confirmed parameters of the requested media types.

Apps can request all available media streams or specify media streams by content type. If all are requested, the signaling connection responds with all media connections available according to the app's requested scopes. For example, if the app has scopes for audio and transcript only, a request for all media will include audio and transcript data but not video, chat, or screen share data.

To request only one media type, specify that media type in the `media_type` field (see `MEDIA_DATA_TYPE`). Use `"media_type": 32` for all. `media_params` are optional — if not specified, default values are used. See *Data type definitions* for options on codecs, resolutions, rates, etc.

```json
{
  "msg_type": 3,
  "protocol_version": 1,
  "sequence": 0,
  "meeting_uuid": "4xxxxxxxxxx",
  "rtms_stream_id": "xxxxxxxxxx",
  "signature": "xxxxxxxxxx",
  "media_type": 32,
  "media_params": {
    "audio": {
      "content_type": 2,
      "sample_rate": 1,
      "channel": 1,
      "codec": 1,
      "data_opt": 1,
      "send_rate": 100
    },
    "video": {
      "codec": 5,
      "resolution": 2,
      "fps": 5
    },
    "deskshare": {
      "codec": 5,
      "resolution": 3,
      "fps": 1
    },
    "transcript": {
      "content_type": 5,
      "src_language": 9,
      "enable_lid": true
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The app sends this message to the media connection to request a connection with the specified media parameters. See `RTMS_MESSAGE_TYPE`. |
| `protocol_version` | int | The RTMS design version. By default, it's 1.0. |
| `sequence` | int | The sequence number of the message. |
| `meeting_uuid` | string | The unique identifier for the session. |
| `rtms_stream_id` | string | The unique identifier of the RTMS stream. Multiple streams are possible for a session if streaming access stops or restarts. |
| `signature` | string | The authentication signature created using app credentials and session details. |
| `media_type` | int | The media type of the stream: audio (1), video (2), screen share (4), transcript (8), chat (16), or all (32). See `MEDIA_DATA_TYPE`. |
| `media_params` *(optional)* | object | The media parameters of the stream that define the media formats. Defaults are used if not specified, and returned in the response. |
| `content_type` | int | The content type of the media stream: RTP (1), raw audio (2), raw video (3), file stream (4), or text (5). See `MEDIA_CONTENT_TYPE`. |
| `sample_rate` *(audio)* | int | The sample rate of the audio stream. See `AUDIO_SAMPLE_RATE`. |
| `channel` *(audio)* | int | The channel of the audio stream: mono (1) or stereo (2). See `AUDIO_CHANNEL`. |
| `codec` *(audio)* | int | The codec of the audio data: L16 (1), G711 (2), G722 (3), or Opus (4). See `MEDIA_PAYLOAD_TYPE`. |
| `data_opt` *(audio)* | int | Defines whether media is separated or merged (e.g., mixed audio vs. separated audio streams). See `MEDIA_DATA_OPTION`. |
| `send_rate` *(audio)* | int | The send rate of the audio stream in ms. Must be a multiple of 20, up to 1000 ms. |
| `codec` *(video)* | int | The codec of the video data, set during the handshake and fixed for the session. Can be JPG or PNG when fps ≤ 5, and H.264 when fps > 5. Default is JPG at fps 5. If fps > 5 is set without a codec, the server defaults to JPG and fps 5. See `MEDIA_PAYLOAD_TYPE`. |
| `codec` *(screen share)* | int | The codec of the screen share data, set during the handshake and fixed for the session. Can be JPG or PNG when fps ≤ 1, and H.264 when fps > 1. Default is JPG at fps 1. If fps > 1 is set without a codec, the server defaults to JPG and fps 1. See `MEDIA_PAYLOAD_TYPE`. |
| `resolution` *(video)* | int | SD (1), HD (2), FHD (3), or QHD (4). Default is HD. See `MEDIA_RESOLUTION`. |
| `resolution` *(screen share)* | int | SD (1), HD (2), FHD (3), or QHD (4). Default is FHD. See `MEDIA_RESOLUTION`. |
| `fps` *(video & screen share)* | int | Frames per second of the stream. Maximum of 30. |
| `src_language` | int | Optional. Language of the transcript. If unspecified, English is the default for the first 30 seconds; if specified, RTMS transcribes the first 30 seconds based on this setting. After 30 seconds, language is auto-detected and overrides this parameter. See `RTMS_TRANSCRIPT_LANGUAGE`. |
| `enable_lid` | bool | Optional. Default `true` (Language Identification enabled). When `false`, Language Identification is disabled and transcription relies solely on `src_language`. |

### Media handshake response

*Sent from the media connection*

The media connection responds with a media handshake response that includes information about the media connections.

```json
{
  "msg_type": 4,
  "protocol_version": 1,
  "status_code": 0,
  "reason": "",
  "sequence": 0,
  "payload_encrypted": true,
  "media_params": {
    "audio": {
      "content_type": 2,
      "sample_rate": 1,
      "channel": 1,
      "codec": 1,
      "data_opt": 1,
      "send_rate": 100
    },
    "video": {
      "content_type": 3,
      "codec": 5,
      "resolution": 2,
      "data_opt": 3,
      "fps": 5
    },
    "deskshare": {
      "content_type": 3,
      "codec": 5,
      "resolution": 3,
      "fps": 1
    },
    "transcript": {
      "content_type": 5,
      "src_language": 9,
      "enable_lid": true
    },
    "chat": {
      "content_type": 5
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The response from the media connection to the app after a handshake attempt. See `RTMS_MESSAGE_TYPE`. |
| `protocol_version` | int | The RTMS design version. By default, it's 1.0. |
| `status_code` | int | Status code of the message. 0 means success. See `RTMS_STATUS_CODE`. |
| `reason` | string | Empty if successful; otherwise the failure reason. |
| `sequence` | int | The sequence number of the message. |
| `payload_encryption` *(optional)* | bool | Default `false` for any TLS connection — the encryption keys are in the signaling handshake response. If `true`, the payload is encrypted. If `false` but the payload protocol is UDP, the payload will still be encrypted. |
| `content_type` | int | The content type of the media. See `MEDIA_CONTENT_TYPE`. |
| `sample_rate` | int | The sample rate of the audio stream. See `AUDIO_SAMPLE_RATE`. |
| `channel` | int | Mono (1) or stereo (2). See `AUDIO_CHANNEL`. |
| `codec` | int | L16 (1), G711 (2), G722 (3), or Opus (4). See `MEDIA_PAYLOAD_TYPE`. |
| `data_opt` | int | Defines whether media is separated or merged. See `MEDIA_DATA_OPTION`. |
| `send_rate` | int | Send rate of the audio stream in ms; multiple of 20, up to 1000 ms. |
| `codec` *(video)* | int | Same rules as in the handshake request (JPG/PNG ≤5fps, H.264 >5fps). See `MEDIA_PAYLOAD_TYPE`. |
| `codec` *(screen share)* | int | Same rules as in the handshake request (JPG/PNG ≤1fps, H.264 >1fps). See `MEDIA_PAYLOAD_TYPE`. |
| `resolution` *(video)* | int | SD/HD/FHD/QHD. Default HD. See `MEDIA_RESOLUTION`. |
| `resolution` *(screen share)* | int | SD/HD/FHD/QHD. Default FHD. See `MEDIA_RESOLUTION`. |
| `fps` *(video & screen share)* | int | Maximum of 30. |
| `src_language` | int | Same behavior as in the handshake request. See `RTMS_TRANSCRIPT_LANGUAGE`. |
| `enable_lid` | bool | Same behavior as in the handshake request. |

### Client ready ACK message

*Sent to the signaling connection*

After the app receives the data handshake response from the media connection, it needs to send a client ready ACK to the signaling connection to indicate that the full handshake has completed and that it is ready to receive media data. Send this only after both the signaling and media connections have been established.

```json
{
  "msg_type": 7,
  "rtms_stream_id": "xxxxxxxxxx"
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The app sends this to acknowledge readiness to receive media. See `RTMS_MESSAGE_TYPE`. |
| `rtms_stream_id` | string | The unique identifier for the RTMS stream. |

### Keep-alive request

*Sent from the media connection*

To maintain stable connections and prevent timeouts, RTMS servers send a keep-alive request to both the signaling and media connections every 10 seconds.

When three keep-alive requests go unanswered, RTMS takes different actions depending on connection type:

- **Signaling connection** — RTMS interrupts both the signaling and media connections, waits one minute for reconnection, and ends the RTMS stream if not restored.
- **Media connections** — RTMS interrupts the media connection, waits 65 seconds for reconnection, and ends the RTMS stream if not restored.

If an app doesn't receive a keep-alive request for 65 seconds, it's recommended to reestablish the connection by resending the signaling handshake request. See *Working with streams*.

```json
{
  "msg_type": 12,
  "timestamp": 1727384349123
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The media connection sends this to confirm the app wants to maintain a connection. See `RTMS_MESSAGE_TYPE`. |
| `timestamp` | unsigned long | The Unix timestamp of the request. |

### Keep-alive response

*Sent to the media connection*

To maintain the connection, an app should respond to the request with the following response. The `timestamp` in the response must match the request.

```json
{
  "msg_type": 13,
  "timestamp": 1727384349123
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The app sends this to the media connection to maintain a connection. See `RTMS_MESSAGE_TYPE`. |
| `timestamp` | unsigned long | The Unix timestamp of the keep-alive request. |

### Subscribe to events

*Sent to the signaling connection*

Send this message to the signaling connection to get data about behavior during sessions.

> **Note:** Some events are sent automatically and don't need to be subscribed to. To ensure your app works as expected, don't subscribe to these events: `FIRST_PACKET_TIMESTAMP = 1`, `MEDIA_CONNECTION_INTERRUPTED = 7`.

This message does not require a response.

```json
{
  "msg_type": 5,
  "events": [
    {
      "event_type": 2,
      "subscribe": true
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The app sends this to subscribe or unsubscribe to in-session events. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | The type of event to subscribe to. See `RTMS_EVENT_TYPE`. |
| `subscribe` | bool | `true` to subscribe, `false` to unsubscribe. |

### Audio data

*Sent from the media connection*

Audio data from the media connection of a participant in a session. It can be either merged audio or individual audio.

```json
{
  "msg_type": 14,
  "content": {
    "user_id": 16778240,
    "user_name": "John Smith",
    "data": "<base64-encoded audio data>",
    "length": 1024,
    "timestamp": 1738392033699
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Audio data sent from the media connection. See `RTMS_MESSAGE_TYPE`. |
| `user_id` | int | Unique identifier of the participant whose audio is included. |
| `user_name` | string | Username of the participant. If `user_id` in the RTP header is 0, no `user_name` is sent. |
| `channel_id` | string | For Zoom Contact Center engagements, the unique identifier of the SIP trunk channel carrying this audio. Each party is on a separate channel. |
| `data` | string | Audio data, base64-encoded binary. |
| `length` | int | Length of the original binary data before base64 encoding. |
| `timestamp` | unsigned long | The Unix timestamp of the data. |

### Video data

*Sent from the media connection*

Video data from the media connection of the active speaker participant in a session.

```json
{
  "msg_type": 15,
  "content": {
    "user_id": 16778240,
    "user_name": "John Smith",
    "data": "<base64-encoded video data>",
    "length": 1024,
    "timestamp": 1738392033699
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Video data sent from the media connection. See `RTMS_MESSAGE_TYPE`. |
| `user_id` | int | Unique identifier of the participant whose video was included. |
| `user_name` | string | Username of the participant. |
| `data` | string | Video data, base64-encoded binary. |
| `length` | int | Length of the original binary data before base64 encoding. |
| `timestamp` | unsigned long | The Unix timestamp of the data. |

### Screen share data

*Sent from the media connection*

Content shared by a participant in a session, sent from the media connection.

```json
{
  "msg_type": 16,
  "content": {
    "user_id": 16778240,
    "user_name": "John Smith",
    "data": "<base64-encoded screen share data>",
    "length": 1024,
    "timestamp": 1738392033699
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Screen share data sent from the media connection. See `RTMS_MESSAGE_TYPE`. |
| `user_id` | int | Unique identifier of the participant who shared their screen. |
| `user_name` | string | Username of the participant who shared their screen. |
| `data` | string | Screen share video data, base64-encoded binary. |
| `length` | int | Length of the original binary data before base64 encoding. |
| `timestamp` | unsigned long | The Unix timestamp of the data. |

### Transcript data

*Sent from the media connection*

Transcript of the spoken audio in a session, sent from the media connection. Messages are sent separately for each participant who has spoken.

```json
{
  "msg_type": 17,
  "content": {
    "user_id": 19778240,
    "user_name": "John Smith",
    "start_time": 1727384100000,
    "end_time": 1727384310000,
    "timestamp": 1727384349000,
    "language": 9,
    "data": "Hi, hello world!"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Transcript data sent from the media connection. See `RTMS_MESSAGE_TYPE`. |
| `user_id` | int | Unique identifier of the participant whose transcript is included. |
| `user_name` | string | Username of the participant. |
| `channel_id` | string | For Zoom Contact Center engagements, the SIP trunk channel carrying this transcript. |
| `start_time` | unsigned long | Unix timestamp of when transcription started. |
| `end_time` | unsigned long | Unix timestamp of when transcription ended. |
| `timestamp` | unsigned long | Unix timestamp of the data. |
| `language` | int | Language of the transcript data. See `RTMS_TRANSCRIPT_LANGUAGE`. |
| `data` | string | The transcript data, UTF-8 encoded string. |

### Chat data

*Sent from the media connection*

> **Note:** Chat data is not supported yet.

Chat data sent from the media connection. Messages are sent separately for all participants who have sent chat messages.

```json
{
  "msg_type": 18,
  "content": {
    "timestamp": 1727384349000,
    "data": "Chat message"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Chat data sent from the media connection. See `RTMS_MESSAGE_TYPE`. |
| `timestamp` | unsigned long | The Unix timestamp of the data. |
| `data` | string | The chat message, UTF-8 encoded string. |

### Session state updated

*Sent from the signaling connection*

The signaling connection sends session state updated events when a new session is added or the state of a session changes. A session can stop and resume during a stream. The `STARTED` state means a brand-new session has started — record the session information locally since each session's state changes separately. This message does not require a response.

```json
{
  "msg_type": 9,
  "state": 1,
  "stop_reason": 1,
  "timestamp": 1727384349123,
  "rtms_session_id": "xxxxxxxxxx"
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when a session has been updated. See `RTMS_MESSAGE_TYPE`. |
| `state` | int | The state of a session within a stream. See `RTMS_SESSION_STATE`. |
| `reason` | int | Why a session status updated; only sent if session state stops. See `RTMS_STOP_REASON`. |
| `timestamp` | unsigned long | Unix timestamp of when the session was updated. |
| `rtms_session_id` | string | Unique identifier for the RTMS session. |

### Session state request

*Sent to the signaling connection*

Apps send this to query the current session state. The signaling connection responds with the current state.

```json
{
  "msg_type": 10,
  "rtms_session_id": "xxxxxxxxxx"
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The app sends this to query the current session state. See `RTMS_MESSAGE_TYPE`. |
| `rtms_session_id` | string | Unique identifier for the RTMS session. |

### Session state response

*Sent from the signaling connection*

Sent in response to a session state request.

```json
{
  "msg_type": 11,
  "rtms_session_id": "xxxxxxxxxx",
  "state": 1,
  "timestamp": 1727384349123
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Response to the session state query. See `RTMS_MESSAGE_TYPE`. |
| `rtms_session_id` | string | Unique identifier for the RTMS session. |
| `state` | int | The state of the current session. See `RTMS_SESSION_STATE`. |
| `timestamp` | unsigned long | Unix timestamp of the request; use to pair requests and responses. |

### Stream state request

*Sent to the signaling connection*

Apps send this to query the current stream state. Streams can be: inactive, active, interrupted, terminating, terminated, paused, or resumed.

```json
{
  "msg_type": 19,
  "rtms_stream_id": "756FF58A-6332-6ECA-E4AE-21F2ABDCB485"
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The app sends this to query the current stream state. See `RTMS_MESSAGE_TYPE`. |
| `rtms_stream_id` | string | Unique identifier of the RTMS stream. |

### Stream state response

*Sent from the signaling connection*

Sent in response to a stream state request.

```json
{
  "msg_type": 20,
  "state": 1,
  "rtms_stream_id": "756FF58A-6332-6ECA-E4AE-21F2ABDCB485",
  "timestamp": 1694204592
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Response to the stream state query. See `RTMS_MESSAGE_TYPE`. |
| `state` | int | Current state of the RTMS stream. See `RTMS_STREAM_STATE`. |
| `rtms_stream_id` | string | Unique identifier for the RTMS stream. |
| `timestamp` | unsigned long | Unix timestamp of the request; use to pair requests and responses. |

### Stream state updated

*Sent from the signaling connection*

```json
{
  "msg_type": 8,
  "state": 1,
  "reason": 1,
  "timestamp": 1727384349123
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when a stream has been updated. See `RTMS_MESSAGE_TYPE`. |
| `state` | int | State of the stream (active, connection issues, needs termination, etc.). See `RTMS_STREAM_STATE`. |
| `reason` | int | Why the stream status was updated. See `RTMS_STOP_REASON`. |
| `timestamp` | unsigned long | Unix timestamp of when the stream was updated. |

### Stream close request

*Sent to the signaling connection*

To gracefully close a stream from the app backend, send a `STREAM_CLOSE_REQ` message through the signaling connection. RTMS responds with `STREAM_CLOSE_RESP` and terminates the stream.

```json
{
  "msg_type": 21,
  "rtms_stream_id": "xxxxxxxxxx"
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The request from the app to close the stream. See `RTMS_MESSAGE_TYPE`. |
| `rtms_stream_id` | string | Unique identifier of the RTMS stream to close. |

### Stream close response

*Sent from the signaling connection*

Confirms the result of a stream close request.

```json
{
  "msg_type": 22,
  "rtms_stream_id": "xxxxxxxxxx",
  "status_code": 0,
  "reason": "OK",
  "timestamp": 1727384349123
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Response after a stream close request. See `RTMS_MESSAGE_TYPE`. |
| `rtms_stream_id` | string | Unique identifier of the RTMS stream. |
| `status_code` | int | Status code of the response. 0 means success. See `RTMS_STATUS_CODE`. |
| `reason` | string | Empty if successful; otherwise the failure reason. |
| `timestamp` | unsigned long | Unix timestamp of when the response was sent. |

### Video subscription request

*Sent to the signaling connection*

To use individual video subscriptions, configure `data_opt` to `4` (`VIDEO_SINGLE_INDIVIDUAL_STREAM`) when establishing the media connection, and subscribe to `PARTICIPANT_VIDEO_ON` and `PARTICIPANT_VIDEO_OFF` events using the *Subscribe to events* message.

To subscribe to an individual participant's video stream, send this message through the signaling connection with the `user_id` obtained from a `PARTICIPANT_VIDEO_ON` event. The RTMS server supports subscribing to a single individual video stream at a time; a new subscription request automatically unsubscribes from the previous individual's stream.

```json
{
  "msg_type": 28,
  "user_id": 16778240,
  "subscribe": true,
  "timestamp": 1738392033699
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | The request to subscribe or unsubscribe from an individual's video stream. See `RTMS_MESSAGE_TYPE`. |
| `user_id` | unsigned int32 | Unique identifier of the participant to subscribe to, obtained from a `PARTICIPANT_VIDEO_ON` event. |
| `subscribe` | bool | `true` to subscribe, `false` to unsubscribe. |
| `timestamp` | unsigned long | Unix timestamp of the request. |

### Video subscription response

*Sent from the signaling connection*

Response to a video subscription request. If successful, the subscribed participant's video stream begins transmitting through the video data socket connection.

```json
{
  "msg_type": 29,
  "user_id": 16778240,
  "status_code": 0,
  "reason": "OK",
  "timestamp": 1738392033699
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Response after a video subscription request. See `RTMS_MESSAGE_TYPE`. |
| `user_id` | unsigned int32 | Unique identifier of the participant subscribed or unsubscribed. |
| `status_code` | int | Status code of the response. 0 means success. See `RTMS_STATUS_CODE`. |
| `reason` | string | Empty if successful; otherwise the failure reason. |
| `timestamp` | unsigned long | Unix timestamp of the response. |

### First timestamp from the signaling connection

*Sent from the signaling connection*

After the signaling connection connects, it sends a message to the app with the first timestamp. Use this timestamp as the start of the session. This message does not require a response.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 1,
    "timestamp": 1727384349123
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Provides the first timestamp for the connection. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | The first timestamp event. See `RTMS_EVENT_TYPE`. |
| `timestamp` | unsigned long | The Unix timestamp sent by the signaling connection. |

### Active speaker change

*Sent from the signaling connection*

Provides timestamps for when a user becomes the primary speaking participant (green box around their tile). This message does not require a response.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 2,
    "timestamp": 1727384349123,
    "user_id": 22334455,
    "user_name": "John Smith"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when the active speaker changes. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | The active speaker changed event. See `RTMS_EVENT_TYPE`. |
| `timestamp` | unsigned long | Unix timestamp of the event. |
| `user_id` | unsigned int32 | The current active speaker's unique identifier. |
| `user_name` | string | The current active speaker's username. |

### Participant joined

*Sent from the signaling connection*

Sent when someone joins the session. This message does not require a response.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 3,
    "timestamp": 1727384349123,
    "participants": [
      { "user_id": "xxxxxxxxxx", "user_name": "John Smith" },
      { "user_id": "xxxxxxxxxx", "user_name": "Alice" }
    ]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when a participant joins a session. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | Participant joined event. See `RTMS_EVENT_TYPE`. |
| `timestamp` | unsigned long | Unix timestamp of when the participant joined. |
| `participants` | array | The participants in the session. |
| `user_id` | unsigned long | Unique identifier of the participant that joined. |
| `user_name` | string | Username of the participant that joined. |

### Participant leave

*Sent from the signaling connection*

Sent when a user leaves a session, including when it ends. This message does not require a response.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 4,
    "timestamp": 1727384349123,
    "participants": [
      { "user_id": "xxxxxxxxxx" },
      { "user_id": "xxxxxxxxxx" }
    ]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when a participant leaves a session. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | Participant left event. See `RTMS_EVENT_TYPE`. |
| `timestamp` | unsigned long | Unix timestamp of when the participant left. |
| `participants` | array | The participants that left the session. |
| `user_id` | unsigned int32 | Unique identifier of the participant who left. |

### Sharing started

*Sent from the signaling connection*

Sent when a user starts sharing their screen, if the app has the DESKSHARE scope. This message does not require a response.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 5,
    "timestamp": 1727384349123,
    "user_id": 1234234567890,
    "user_name": "John Smith"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when a participant starts sharing their screen. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | Sharing started event. See `RTMS_EVENT_TYPE`. |
| `timestamp` | unsigned long | Unix timestamp when screen sharing started. |
| `user_id` | unsigned int32 | Unique identifier of the participant that started sharing. |
| `user_name` | string | Username of the participant that started screen sharing. |

### Sharing stopped

*Sent from the signaling connection*

Sent when a user stops sharing their screen, if the app has the DESKSHARE scope. This message does not require a response.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 6,
    "timestamp": 1727384349123
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when a participant stops sharing their screen. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | Sharing stopped event. See `RTMS_EVENT_TYPE`. |
| `timestamp` | unsigned long | Unix timestamp when screen sharing stopped. |

### Participant video on

*Sent from the signaling connection*

Sent when a participant enables their camera and is actively streaming video. Use the `user_id` to send a video subscription request. This message does not require a response.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 8,
    "timestamp": 1727384349123,
    "participants": [
      { "user_id": 16778240 },
      { "user_id": 33556610 }
    ]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when a participant turns their camera on. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | Participant camera on event. See `RTMS_EVENT_TYPE`. |
| `timestamp` | unsigned long | Unix timestamp of the event. |
| `participants` | array | List of participants who turned their camera on. |
| `user_id` | unsigned int32 | Unique identifier of the participant in the session. |

### Participant video off

*Sent from the signaling connection*

Sent when a participant turns off their camera; no video stream is being sent from that participant. This message does not require a response.

```json
{
  "msg_type": 6,
  "event": {
    "event_type": 9,
    "timestamp": 1727384349123,
    "participants": [
      { "user_id": 16778240 }
    ]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `msg_type` | int | Sent when a participant turns their camera off. See `RTMS_MESSAGE_TYPE`. |
| `event_type` | int | Participant camera off event. See `RTMS_EVENT_TYPE`. |
| `timestamp` | unsigned long | Unix timestamp of the event. |
| `participants` | array | List of participants who turned their camera off. |

---

## Data type definitions

Use these data type definitions as a reference for event signaling and metadata requests and responses.

> **Note:** For data type definitions, use the representative enum integers. Example: send `msg_type: 1`, not `msg_type: SIGNALING_HAND_SHAKE_REQ`.

### RTMS_MESSAGE_TYPE

Indicates the type of message in signaling handshake requests and responses, event subscription requests, metadata exchanges, and session status control commands.

```c
enum RTMS_MESSAGE_TYPE
{
    UNDEFINED = 0,
    SIGNALING_HAND_SHAKE_REQ = 1,    // Signaling connection handshake request
    SIGNALING_HAND_SHAKE_RESP = 2,   // Response to signaling connection handshake request
    DATA_HAND_SHAKE_REQ = 3,         // Media data connection handshake request
    DATA_HAND_SHAKE_RESP = 4,        // Response of media data connection handshake request
    EVENT_SUBSCRIPTION = 5,          // Events to subscribe or unsubscribe to
    EVENT_UPDATE = 6,                // Specific event occurred
    CLIENT_READY_ACK = 7,            // Client ready to receive media data
    STREAM_STATE_UPDATE = 8,         // Stream state changed
    SESSION_STATE_UPDATE = 9,        // Session state updated, e.g. paused/resumed
    SESSION_STATE_REQ = 10,          // Request the session state
    SESSION_STATE_RESP = 11,         // Response of the session state request
    KEEP_ALIVE_REQ = 12,             // Keep-alive request message
    KEEP_ALIVE_RESP = 13,            // Keep-alive response message
    MEDIA_DATA_AUDIO = 14,           // Audio data is being transmitted
    MEDIA_DATA_VIDEO = 15,           // Video data is being transmitted
    MEDIA_DATA_SHARE = 16,           // Sharing data is being transmitted
    MEDIA_DATA_TRANSCRIPT = 17,      // Transcripts are being transmitted
    MEDIA_DATA_CHAT = 18,            // Chat messages are being transmitted
    STREAM_STATE_REQ = 19,           // Request the stream state
    STREAM_STATE_RESP = 20,          // Response to the stream state request
    STREAM_CLOSE_REQ = 21,           // Close stream request from receiver
    STREAM_CLOSE_RESP = 22,          // Response of the close stream request
    META_DATA_AUDIO = 23,            // Audio-related metadata is being transmitted
    META_DATA_VIDEO = 24,            // Reserved. Video-related metadata is being transmitted
    META_DATA_SHARE = 25,            // Reserved. Sharing-related metadata is being transmitted
    META_DATA_TRANSCRIPT = 26,       // Reserved. Transcript-related metadata is being transmitted
    META_DATA_CHAT = 27,             // Reserved. Chat-related metadata is being transmitted
    VIDEO_SUBSCRIPTION_REQ = 28,     // Subscribe or unsubscribe from a user's video
    VIDEO_SUBSCRIPTION_RESP = 29     // Response of video subscribe/unsubscribe request
}
```

### RTMS_EVENT_TYPE

Indicates the type of event captured in the metadata from the signaling connection.

```c
enum RTMS_EVENT_TYPE
{
    UNDEFINED = 0,
    FIRST_PACKET_TIMESTAMP = 1,       // Indicates the first packet capture timestamp
    ACTIVE_SPEAKER_CHANGE = 2,        // Indicates the most recent active speaker
    PARTICIPANT_JOIN = 3,             // New participant joined this meeting
    PARTICIPANT_LEAVE = 4,            // Participant is leaving this meeting
    SHARING_START = 5,                // Sharing has started in the meeting
    SHARING_STOP = 6,                 // Sharing has stopped in the meeting
    MEDIA_CONNECTION_INTERRUPTED = 7, // A media type connection was interrupted
    PARTICIPANT_VIDEO_ON = 8,         // A participant's camera is turned on
    PARTICIPANT_VIDEO_OFF = 9         // A participant's camera is turned off
}
```

### RTMS_ZCC_VOICE_EVENT_TYPE

Indicates the type of event for Zoom Contact Center voice sessions.

```c
enum RTMS_ZCC_VOICE_EVENT_TYPE
{
    UNDEFINED = 0,
    CONSUMER_ANSWERED = 8,                    // A consumer answered a call
    CONSUMER_END = 9,                         // A consumer ended a call
    USER_ANSWERED = 10,                       // A user answered a call, e.g. Agent
    USER_END = 11,                            // A user ended a call
    USER_HOLD = 12,                           // A user placed a call on hold
    USER_UNHOLD = 13,                         // A user resumed a call from hold
    MONITOR_STARTED = 14,
    MONITOR_TRANSITIONED = 15,
    MONITOR_ENDED = 16,
    TAKEOVER_STARTED = 17,
    TRANSFER_INITIATED = 18,
    TRANSFER_CANCELED = 19,
    TRANSFER_ACCEPTED = 20,
    TRANSFER_COMPLETED = 21,
    TRANSFER_REJECTED = 22,
    TRANSFER_TIMEOUT = 23,
    CONFERENCE_CANCELED = 24,
    CONFERENCE_PARTICIPANT_CANCELED = 25,
    CONFERENCE_PARTICIPANT_INVITED = 26,
    CONFERENCE_PARTICIPANT_REJECTED = 27,
    CONFERENCE_PARTICIPANT_TIMEOUT = 28,
    CONFERENCE_PARTICIPANT_LEFT = 29,
}
```

### RTMS_STATUS_CODE

Indicates the status of handshake requests.

```c
enum RTMS_STATUS_CODE
{
    STATUS_OK = 0,
    STATUS_INVALID_MESSAGE_TYPE = 1,
    STATUS_INVALID_RTMS_STREAM_ID = 2,
    STATUS_INVALID_SIGNATURE = 3,
    STATUS_INVALID_PAYLOAD = 4,
    STATUS_INVALID_EVENTS = 5,
    STATUS_INVALID_EVENT_TYPE = 6,
    STATUS_INVALID_MEDIA_TYPE = 7,
    STATUS_DUPLICATE_SIGNAL_REQUEST = 8,
    STATUS_MEDIA_TYPE_AUDIO_NOT_SUPPORT = 9,
    STATUS_MEDIA_TYPE_VIDEO_NOT_SUPPORT = 10,
    STATUS_MEDIA_TYPE_DESKSHARE_NOT_SUPPORT = 11,
    STATUS_MEDIA_TYPE_TRANSCRIPT_NOT_SUPPORT = 12,
    STATUS_MEDIA_TYPE_CHAT_NOT_SUPPORT = 13,
    STATUS_MEDIA_TYPE_INVALID_VALUE = 14,
    STATUS_MEDIA_DATA_ALL_CONNECTION_EXIST = 15,
    STATUS_DUPLICATE_MEDIA_DATA_CONNECTION = 16,
    STATUS_INVALID_MEDIA_PARAMS = 17,
    STATUS_INVALID_MEDIA_AUDIO_PARAMS = 18,
    STATUS_INVALID_MEDIA_AUDIO_CONTENT_TYPE = 19,
    STATUS_INVALID_MEDIA_AUDIO_SAMPLE_RATE = 20,
    STATUS_INVALID_MEDIA_AUDIO_CHANNEL = 21,
    STATUS_INVALID_MEDIA_AUDIO_CODEC = 22,
    STATUS_INVALID_MEDIA_AUDIO_DATA_OPT = 23,
    STATUS_INVALID_MEDIA_AUDIO_SEND_RATE = 24,
    STATUS_INVALID_MEDIA_VIDEO_PARAMS = 25,
    STATUS_INVALID_MEDIA_VIDEO_CONTENT_TYPE = 26,
    STATUS_INVALID_MEDIA_VIDEO_CODEC = 27,
    STATUS_INVALID_MEDIA_VIDEO_RESOLUTION = 28,
    STATUS_INVALID_MEDIA_VIDEO_DATA_OPT = 29,
    STATUS_INVALID_MEDIA_VIDEO_FPS = 30,
    STATUS_INVALID_MEDIA_DESKSHARE_PARAMS = 31,
    STATUS_INVALID_MEDIA_DESKSHARE_CONTENT_TYPE = 32,
    STATUS_INVALID_MEDIA_DESKSHARE_CODEC = 33,
    STATUS_INVALID_MEDIA_DESKSHARE_RESOLUTION = 34,
    STATUS_INVALID_MEDIA_DESKSHARE_FPS = 35,
    STATUS_INVALID_MEDIA_TRANSCRIPT_PARAMS = 36,
    STATUS_INVALID_MEDIA_TRANSCRIPT_CONTENT_TYPE = 37,
    STATUS_INVALID_MEDIA_CHAT_PARAMS = 38,
    STATUS_INVALID_MEDIA_CHAT_CONTENT_TYPE = 39,
    STATUS_INVALID_RTMS_SESSION_ID = 40,
    STATUS_INVALID_CLIENT_READY_ACK = 41,
    STATUS_INVALID_EVENT_SUBSCRIBE = 42,
    STATUS_INVALID_MEDIA_TRANSCRIPT_SOURCE_LANGUAGE = 43,
    STATUS_DUPLICATE_VIDEO_SUBSCRIPTION = 44,
    STATUS_INTERNAL_EXCEPTION = 45,
}
```

### RTMS_SESSION_STATE

Indicates the current session state during RTMS session updates.

```c
enum RTMS_SESSION_STATE
{
    INACTIVE = 0,     // Default state
    INITIALIZE = 1,   // A new session is initializing
    STARTED = 2,      // A new session is started
    PAUSED = 3,       // A session is paused
    RESUMED = 4,      // A session is resumed
    STOPPED = 5       // A session is stopped
}
```

### RTMS_STREAM_STATE

Indicates the current state of the RTMS stream.

```c
enum RTMS_STREAM_STATE
{
    INACTIVE = 0,     // Default state
    ACTIVE = 1,       // Media data has started to transmit, RTMS -> client
    INTERRUPTED = 2,  // Signal or data connection encountered a problem
    TERMINATING = 3,  // Notifying client stream needs to be terminated
    TERMINATED = 4,   // Stream is terminated
    PAUSED = 5,       // Stream is paused
    RESUMED = 6       // Stream is resumed
}
```

### RTMS_STOP_REASON

Indicates the failure status for handshake requests or the reasons for a session to end.

```c
enum RTMS_STOP_REASON
{
    UNDEFINED = 0,                                    // Default value, means no value
    STOP_BC_HOST_TRIGGERED = 1,                        // Stopped when triggered by host
    STOP_BC_USER_TRIGGERED = 2,                         // Stopped when triggered by user
    STOP_BC_USER_LEFT = 3,                              // Stopped when app user left meeting
    STOP_BC_USER_EJECTED = 4,                           // Stopped when app user ejected by meeting host
    STOP_BC_HOST_DISABLED_APP = 5,                      // Stopped when host disabled app user or entire app
    STOP_BC_MEETING_ENDED = 6,                          // Stopped when meeting is ended
    STOP_BC_STREAM_CANCELED = 7,                        // Stopped when stream canceled by participant request
    STOP_BC_STREAM_REVOKED = 8,                         // Stopped when stream is revoked; assets must be deleted immediately
    STOP_BC_ALL_APPS_DISABLED = 9,                      // Stopped when host disabled all apps in the meeting
    STOP_BC_INTERNAL_EXCEPTION = 10,                    // Stopped due to internal exceptions
    STOP_BC_CONNECTION_TIMEOUT = 11,                    // Stopped when the connection timed out
    STOP_BC_INSTANCE_CONNECTION_INTERRUPTED = 12,       // Stopped when an instance call connection is interrupted
    STOP_BC_SIGNAL_CONNECTION_INTERRUPTED = 13,         // Stopped when RTMS signaling connection is interrupted
    STOP_BC_DATA_CONNECTION_INTERRUPTED = 14,           // Stopped when RTMS data connection is interrupted
    STOP_BC_SIGNAL_CONNECTION_CLOSED_ABNORMALLY = 15,   // Stopped when signaling connection is closed abnormally by app
    STOP_BC_DATA_CONNECTION_CLOSED_ABNORMALLY = 16,     // Stopped when data connection is closed abnormally by app
    STOP_BC_EXIT_SIGNAL = 17,                           // Stopped when received exit signal
    STOP_BC_AUTHENTICATION_FAILURE = 18,                // Stopped due to authentication failure
    STOP_BC_AWAIT_RECONNECTION_TIMEOUT = 19,            // Stopped when awaiting reconnection timed out
    STOP_BC_RECEIVER_REQUEST_CLOSE = 20,                // Stopped when received stream close request from receiver
    STOP_BC_CUSTOMER_DISCONNECTED = 21,                 // Stopped when triggered by customer (Zoom Contact Center Voice)
    STOP_BC_AGENT_DISCONNECTED = 22,                    // Stopped when triggered by agent (Zoom Contact Center Voice)
    STOP_BC_ADMIN_DISABLED_APP = 23,                    // Stopped when admin disabled app
    STOP_BC_KEEP_ALIVE_TIMEOUT = 24,                    // Stopped when no response for three consecutive keep-alive requests
    STOP_BC_MANUAL_API_TRIGGERED = 25,                  // Stopped when triggered by API (Zoom Contact Center Voice)
    STOP_BC_STREAMING_NOT_SUPPORTED = 26,               // Stopped when the queue doesn't support streaming (Zoom Contact Center Voice)
}
```

### MEDIA_CONTENT_TYPE

Indicates the media formats in handshake requests and responses.

```c
enum MEDIA_CONTENT_TYPE
{
    UNDEFINED = 0,
    RTP = 1,          // Real-time audio and video
    RAW_AUDIO = 2,    // Real-time audio
    RAW_VIDEO = 3,    // Real-time video
    FILE_STREAM = 4,  // File stream
    TEXT = 5          // Media data is text based, such as Chat and Transcripts
}
```

### MEDIA_DATA_TYPE

Indicates the media data formats in handshake requests and responses.

```c
enum MEDIA_DATA_TYPE
{
    UNDEFINED = 0,
    AUDIO = 0x01,            // 1
    VIDEO = 0x01 << 1,       // 2
    DESKSHARE = 0x01 << 2,   // 4
    TRANSCRIPT = 0x01 << 3,  // 8
    CHAT = 0x01 << 4,        // 16
    ALL = 0x01 << 5,         // 32
}
```

### MEDIA_DATA_OPTION

Indicates the media parameters for the audio and video media connections in handshake requests and responses.

```c
enum MEDIA_DATA_OPTION
{
    UNDEFINED = 0,
    // Data will be a mixed audio stream; only one data packet message will be sent within a specific transmission interval
    AUDIO_MIXED_STREAM = 1,
    // Data will be multiple user audio streams; one or multiple data packet message(s) will be sent within a specific transmission interval
    AUDIO_MULTI_STREAMS = 2,
    // Data will be a single video stream of the present active speaker; no subscription needed
    VIDEO_SINGLE_ACTIVE_STREAM = 3,
    // Data will be a single video stream of a specified individual; manual subscription is required and allows subscription to only one individual at a time
    VIDEO_SINGLE_INDIVIDUAL_STREAM = 4,
}
```

### MEDIA_PAYLOAD_TYPE

Indicates the media payload formats in handshake requests and responses.

```c
enum MEDIA_PAYLOAD_TYPE
{
    UNDEFINED = 0,
    L16 = 1,   // Audio, uncompressed raw data
    G711 = 2,  // Audio
    G722 = 3,  // Audio
    OPUS = 4,  // Audio
    JPG = 5,   // Video and Sharing, when fps <= 5
    PNG = 6,   // Video and Sharing, when fps <= 5
    H264 = 7   // Video and Sharing, when fps > 5
}
```

### MEDIA_RESOLUTION

Indicates the media resolution for the audio, video, and screen share media connections in handshake requests and responses.

```c
enum MEDIA_RESOLUTION
{
    SD = 1,    // 480p or 360p, 854x480 or 640x360
    HD = 2,    // 720p, 1280 x 720
    FHD = 3,   // 1080p, 1920 x 1080
    QHD = 4    // 2K, 2560 x 1440
}
```

### AUDIO_SAMPLE_RATE

Indicates the audio sample rate for the audio object in handshake requests and responses.

```c
enum AUDIO_SAMPLE_RATE
{
    SR_8K = 0,
    SR_16K = 1,
    SR_32K = 2,
    SR_48K = 3
}
```

### AUDIO_CHANNEL

Indicates the audio channel configuration for the audio object in handshake requests and responses.

```c
enum AUDIO_CHANNEL
{
    MONO = 1,
    STEREO = 2
}
```

### TRANSMISSION_PROTOCOL

Indicates the transmission protocol in handshake requests and responses. Currently only WebSockets is supported.

```c
enum TRANSMISSION_PROTOCOL
{
    WEBSOCKET = 1,
    RTMP = 2,
    UDP = 3,
    WEBRTC = 4
}
```

### RTMS_DATA_MESSAGE_ATTRIBUTE

Indicates the attribute of a data message, used to signal whether the data is new, an update, or a deletion.

```c
enum RTMS_DATA_MESSAGE_ATTRIBUTE
{
    ATTR_NONE = 0,
    ATTR_NEW = 1,
    ATTR_UPDATE = 2,
    ATTR_DELETE = 3,
}
```

### RTMS_TRANSCRIPT_LANGUAGE

Indicates the language of the transcript in handshake requests and responses.

```c
enum RTMS_TRANSCRIPT_LANGUAGE
{
    LANGUAGE_ID_NONE = -1,
    LANGUAGE_ID_ARABIC = 0,
    LANGUAGE_ID_BENGALI = 1,
    LANGUAGE_ID_CANTONESE = 2,
    LANGUAGE_ID_CATALAN = 3,
    LANGUAGE_ID_CHINESE_SIMPLIFIED = 4,
    LANGUAGE_ID_CHINESE_TRADITIONAL = 5,
    LANGUAGE_ID_CZECH = 6,
    LANGUAGE_ID_DANISH = 7,
    LANGUAGE_ID_DUTCH = 8,
    LANGUAGE_ID_ENGLISH = 9,
    LANGUAGE_ID_ESTONIAN = 10,
    LANGUAGE_ID_FINNISH = 11,
    LANGUAGE_ID_FRENCH_CANADA = 12,
    LANGUAGE_ID_FRENCH_FRANCE = 13,
    LANGUAGE_ID_GERMAN = 14,
    LANGUAGE_ID_HEBREW = 15,
    LANGUAGE_ID_HINDI = 16,
    LANGUAGE_ID_HUNGARIAN = 17,
    LANGUAGE_ID_INDONESIAN = 18,
    LANGUAGE_ID_ITALIAN = 19,
    LANGUAGE_ID_JAPANESE = 20,
    LANGUAGE_ID_KOREAN = 21,
    LANGUAGE_ID_MALAY = 22,
    LANGUAGE_ID_PERSIAN = 23,
    LANGUAGE_ID_POLISH = 24,
    LANGUAGE_ID_PORTUGUESE = 25,
    LANGUAGE_ID_ROMANIAN = 26,
    LANGUAGE_ID_RUSSIAN = 27,
    LANGUAGE_ID_SPANISH = 28,
    LANGUAGE_ID_SWEDISH = 29,
    LANGUAGE_ID_TAGALOG = 30,
    LANGUAGE_ID_TAMIL = 31,
    LANGUAGE_ID_TELUGU = 32,
    LANGUAGE_ID_THAI = 33,
    LANGUAGE_ID_TURKISH = 34,
    LANGUAGE_ID_UKRAINIAN = 35,
    LANGUAGE_ID_VIETNAMESE = 36
}
```

## Handling media data

Realtime Media Streams (RTMS) delivers audio, video, screen share, and transcript data from Zoom meetings and webinars over WebSocket connections between your application and the RTMS servers.

After establishing a connection to the RTMS server, your application receives media data based on:

The scopes configured for your app
The formats specified in your media handshake request
The availability of data in the meeting or webinar
Each media data type has specific formats and best practices for processing the data efficiently.

### Audio

Audio data is available per participant and as a merged packet of all participants.

By default, audio data is sent as uncompressed raw PCM (L16) data with a 16kHz sample rate and mono channels.

The RTMS server sends audio data packets from participants in base64-encoded binary format. Each packet of data contains the user's participant identifier (user_id), username (user_name), and the timestamp (timestamp) of the audio data.

Example audio packet:
{
  "msg_type": 14,
  "content": {
    "user_id": 16778240,
    "user_name": "John Smith",
    "data": "Hw1kDacNAA4sDkMOAQ5eDekMgAzXCw0L4Al4CDwHBAayBEwDmwHD/wn+rfyQ+3z6Z/k4+Ef3jvb09aj1YPUF9QL1OfVt9eH1f/YE96P3jPib+dX6Pvyr/ef+IABcAZ4CmQN3BFAF6QVxBs0G9wbjBqYGXwYFBm8FxwT/Aw4DHAIkARYA7v6o/T382/qq+YD4fPd99mz1p/Qq9KTzcfNv807zcPPQ8z70yfQ89az1SPbO9m/3Lfjf+I75M/rz+pT7KPzs/In9Fv7G/lP/q/8GAG4AtgBHAcABDQKtAkwDIgRQBYQGrgfyCEgKigvDDP4NFw/8D78QhBErEqoS/BL5EsYSfRLnEXARwhCMD1kO8ww8C5gJ5gfrBe8D3AGp/7P9IPyY+hL5t/dl9mv10fQ89NjzvvO78/HzbfTb9F71I/bw9vL3Kvlh+pX71/wr/m//owDCAbQCkwNoBPYEYQWxBZ0FZQUdBYkEBgRkA64CAgIdAT0AZf+T/tD93vz9+xf7B/o8+WX4pvcE90L2n/VM9d70pPSe9IL0nfTa9BX1cfXK9QP2S/a69hH3cPfx91P4w/hO+cr5XPr2+l/71/t9/AP9f/0R/p/+Pv/5/7IAWAH+AeMCAwQ7BaAG+wcmCZEKKQy8DT4PWhBXEVYSVBOgFM0VMxZSFhYW4BXTFUMVNBSzEtIQJg99Da0LogkXB40ESgJCAHj+ivyA+qn4KfcH9hr1JvRf89byq/Lt8kjzhvPy85P0n/X/9kn4lvni+kj84P1S/4wAuwHUAvcD9wS/BUwGaAZcBmcGTQb5BUkFQgQzAzkCVQEgALX+U/3N+4L6XfkU+Nj2o/WB9MTzOfO38g==",
    "timestamp": 1738392033699
  }
}
Send rate
The default interval is 20ms between audio packets. You can configure this in multiples of 20ms, up to a maximum of 1000ms. If you specify an interval above 1000ms in handshake requests, RTMS will change it to 1000ms.

Timestamps
Timestamps denote the creation time on Zoom's server. The timestamp for each audio packet changes relative to the send_rate defined by the handshake request.

If the send_rate is set to 20ms (default), the timestamp for each audio packet will change by 20ms.

When working with streaming audio, timestamps are useful in determining the sequence of messages. Use timestamps to

Infer the period of time where a user might be muted
Match timestamps with video and screen share data to combine, or mux, the audio, video, and screen share frames
User IDs and timestamps
When selecting multiple streams, your application will receive an audio stream for each participant. By sending separate streams, RTMS enables your app to perform audio mixing, isolation, and individual analysis.

Each user will have a unique user_id and their own incremental timestamp.

For merged audio, the user_id will be 0.

Buffered audio
When a meeting.rtms_started, or webinar.rtms_started, webhook event is received, the RTMS server starts buffering audio packets, and the timestamps start to increment, while the signaling connection is made. The RTMS server buffers audio up to 60 seconds while the signaling and media connections are established. Once the connections are established, the buffered audio packets are delivered.

To determine the amount of buffered data, calculate the difference between the timestamp of the rtms_started event and the first packet of audio data.

buffer_duration = firstPacketTimestamp - rtmsStartedEventTs

Note

Video data is not buffered, and its timestamps begin incrementing as soon as the connections are established. As a result, the audio and video timestamps will be offset by the duration of the buffered audio. Take this offset into account when syncing audio and video data.

Best practices
When a meeting or webinar starts, capture the first timestamp from the signaling connection. This denotes the start of the meeting or webinar.

When participants mute their microphones, the RTMS server stops sending audio packets for that user. Use timestamps to detect these gaps and insert silence if needed for your application.

When working with pulse-coded modulation (PCM) audio consider the following:

The size of raw PCM buffer and the storage it might take up without compression
That you may need to convert the audio to WAV format to utilize services such as live streaming or speech to text transcription.
That compression to lossy formats, such as mp3, requires the entire audio file to be completed before compression. We recommend you compress the audio after the meeting, or webinar, has ended.

### Video

Video data is sent as a single video stream of the active speaker.

Supported resolutions:

SD: 480p (854×480) or 360p (640×360)
HD: 720p (1280×720)
FHD: 1080p (1920×1080)
QHD: 2K (2560×1440)
Video resolution may change dynamically based on participants' hardware capabilities and network conditions.

The RTMS server sends video data packets in base64-encoded binary format. Each packet of data contains the user's participant identifier (user_id), username (user_name), and the timestamp (timestamp) of the video data.

Example video packet:
{
    "msg_type": 15,
    "content": {
        "user_id": 16778240,
        "user_name": "John Smith",
        "data": "Hw1kDacNAA4sDkMOAQ5eDekMgAzXCw0L4Al4CDwHBAayBEwDmwHD/wn+rfyQ+3z6Z/k4+Ef3jvb09aj1YPUF9QL1OfVt9eH1f/YE96P3jPib+dX6Pvyr/ef+IABcAZ4CmQN3BFAF6QVxBs0G9wbjBqYGXwYFBm8FxwT/Aw4DHAIkARYA7v6o/T382/qq+YD4fPd99mz1p/Qq9KTzcfNv807zcPPQ8z70yfQ89az1SPbO9m/3Lfjf+I75M/rz+pT7KPzs/In9Fv7G/lP/q/8GAG4AtgBHAcABDQKtAkwDIgRQBYQGrgfyCEgKigvDDP4NFw/8D78QhBErEqoS/BL5EsYSfRLnEXARwhCMD1kO8ww8C5gJ5gfrBe8D3AGp/7P9IPyY+hL5t/dl9mv10fQ89NjzvvO78/HzbfTb9F71I/bw9vL3Kvlh+pX71/wr/m//owDCAbQCkwNoBPYEYQWxBZ0FZQUdBYkEBgRkA64CAgIdAT0AZf+T/tD93vz9+xf7B/o8+WX4pvcE90L2n/VM9d70pPSe9IL0nfTa9BX1cfXK9QP2S/a69hH3cPfx91P4w/hO+cr5XPr2+l/71/t9/AP9f/0R/p/+Pv/5/7IAWAH+AeMCAwQ7BaAG+wcmCZEKKQy8DT4PWhBXEVYSVBOgFM0VMxZSFhYW4BXTFUMVNBSzEtIQJg99Da0LogkXB40ESgJCAHj+ivyA+qn4KfcH9hr1JvRf89byq/Lt8kjzhvPy85P0n/X/9kn4lvni+kj84P1S/4wAuwHUAvcD9wS/BUwGaAZcBmcGTQb5BUkFQgQzAzkCVQEgALX+U/3N+4L6XfkU+Nj2o/WB9MTzOfO38g==",
        "timestamp": 1738392033699
    }
}
Individual participant stream
By default, video streams the active speaker. To receive video from a specific participant instead, see Stream a single participant's video.

Stop video behavior
When a user stop sharing video, the RTMS server will stop sending video packets until data is available again. If all users have stopped sharing video no video data will be sent because no video data is available. If you're recording the meeting or webinar to be played back, you'll need to add in filler frames during the periods when there is no video data when combining, or muxing, audio, video, and screen share data using timestamps. For more information, see Combining media data.

Codecs
Video data can be in JPG or PNG format when the frames per second (fps) is lower than or equal to 5 fps. Video data will be in H.264 format when the fps is greater than 5 fps up to the maximum of 30 fps.

Combining media data
Video data is sent separate from audio and screen share data. Combine, or mux, these data formats using tools like ffmpeg and gstreamer for a playable file. Use our recording sample apps as a reference for muxing.

Timestamps
Timestamps denote the creation time on Zoom's server. The interval at which the timestamp increases depends on the fps settings specified in the media handshake request. If the fps is set at 25, the timestamp should increase at 40ms per video packet.

Timestamps are essential to sync video, audio, and screen share data and can be used to determine the order of frames. Timestamps can also be used to:

Infer the period of time where a user has their video turned off
Match timestamps with audio and screen share data to combine, or mux, the audio, video, and screen share frames
Sample video frames for downsampling
Determine fps
Best practices
H.264 format has a large disk size footprint. When handling a larger amount of simultaneous writing to disk, be mindful of the available disk space, network bandwidth available, and disk I/O throughput. In scenarios where you might be handling multiple streams, consider a distributed processing approach.

In scenarios where real-time data is not essential, consider processing data after the meeting or webinar to prevent unnecessary local resource usage by your application.

### Transcripts

Transcript data is available per participant with attribution, also called diarization.

Transcripts arrive continuously as speech is detected and processed in real time.

The RTMS server sends transcript data packets from each participant as text data with the participant's identifier (user_id), username (user_name), timestamp, and language.

Example transcript packet
{
    "msg_type": 17,
    "content": {
        "user_id": 19778240,
        "user_name": "John Smith",
        "start_time": 1727384100000,
        "end_time": 1727384310000,
        "timestamp": 1727384349000,
        "language": 9,
        "data": "Hi, hello world!"
    }
}
Languages
The language field provides the automatically detected language spoken. When switching from one language to another, it typically takes 10-30 seconds for automatic detection to identify the new language.

Timestamps
Timestamps are sent when the sentence/utterance begins. Use this to create a log of when the user began speaking.

Best practices
As Zoom's transcription optimizes for low latency, it may be helpful to post-process text transcripts into final assets.

In sentence detection, pauses in speech can sometimes be mistaken as an end of a sentence.

Combining multiple transcript messages using message interval and timeouts is a useful strategy to combine disjointed sentences.

