using System;
using System.Text;
using NativeWebSocket;
using UnityEngine;

namespace OneSlash.Client.Network
{
    public class WsClient : MonoBehaviour
    {
        [SerializeField] private string serverUrl = "ws://localhost:8080";

        private WebSocket websocket;

        public bool IsConnected => websocket != null && websocket.State == WebSocketState.Open;

        public event Action<SnapshotMessage> OnSnapshotReceived;

        public async void Connect()
        {
            if (websocket != null)
            {
                return;
            }

            websocket = new WebSocket(serverUrl);

            websocket.OnOpen += () =>
            {
                Debug.Log("[WsClient] Connected");
            };

            websocket.OnError += (error) =>
            {
                Debug.LogError("[WsClient] Error: " + error);
            };

            websocket.OnClose += (code) =>
            {
                Debug.LogWarning("[WsClient] Closed with code: " + code);
                websocket = null;
            };

            websocket.OnMessage += (bytes) =>
            {
                string json = Encoding.UTF8.GetString(bytes);
                Debug.Log("[WsClient] Received: " + json);

                SnapshotMessage snapshot = JsonUtility.FromJson<SnapshotMessage>(json);
                if (snapshot != null && snapshot.type == "snapshot")
                {
                    OnSnapshotReceived?.Invoke(snapshot);
                }
            };

            await websocket.Connect();
        }

        public async void SendInput(InputMessage message)
        {
            if (!IsConnected)
            {
                return;
            }

            string json = JsonUtility.ToJson(message);
            await websocket.SendText(json);
        }

        private async void OnApplicationQuit()
        {
            if (websocket != null)
            {
                await websocket.Close();
            }
        }

        private void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            websocket?.DispatchMessageQueue();
#endif
        }
    }
}
