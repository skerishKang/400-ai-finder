/*
 * citizen-content-adapter.js
 * Official latest content adapter for Buk-gu AI Agent.
 * Simulates async API calls to fetch real-time official content
 * and maintains an in-memory state for local demonstrations.
 */

(function () {
  "use strict";

  // In-memory data store to mock the backend
  var _store = {
    boardPosts: [
      { id: 1, title: "주차장 불편사항 건의", author: "김**", date: "2026-07-09", status: "답변완료" },
      { id: 2, title: "공원 시설물 보수 요청", author: "이**", date: "2026-07-10", status: "접수" }
    ]
  };

  /**
   * Helper to simulate network latency
   * @param {number} ms 
   */
  function _delay(ms) {
    return new Promise(function(resolve) {
      setTimeout(resolve, ms);
    });
  }

  var CitizenContentAdapter = {
    /**
     * Fetch current board posts
     * @returns {Promise<Array>}
     */
    getBoardPosts: function() {
      return _delay(400).then(function() {
        // Return a copy to prevent direct mutation
        return JSON.parse(JSON.stringify(_store.boardPosts)).reverse();
      });
    },

    /**
     * Submit a new board post
     * @param {Object} data { title: string, content: string, author: string }
     * @returns {Promise<Object>}
     */
    submitBoardPost: function(data) {
      return _delay(800).then(function() {
        var newPost = {
          id: _store.boardPosts.length + 1,
          title: data.title,
          author: data.author || "익명",
          date: new Date().toISOString().split("T")[0],
          status: "접수"
        };
        _store.boardPosts.push(newPost);
        return newPost;
      });
    }
  };

  window.CitizenContentAdapter = CitizenContentAdapter;
})();
