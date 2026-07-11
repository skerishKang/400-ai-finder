/*
 * citizen-content-adapter.js
 * Versioned content adapter for the Buk-gu AI Agent demo.
 * Board data is intentionally marked local_demo; live answer freshness comes
 * from /api/mvp/ask and must never be implied by these in-memory fixtures.
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

  var LOCAL_METADATA = Object.freeze({
    sourceUrl: "",
    retrievedAt: null,
    freshnessState: "local_demo"
  });

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
    getSourceMetadata: function() {
      return {
        sourceUrl: LOCAL_METADATA.sourceUrl,
        retrievedAt: LOCAL_METADATA.retrievedAt,
        freshnessState: LOCAL_METADATA.freshnessState
      };
    },

    getBoardSnapshot: function() {
      return _delay(400).then(function() {
        return {
          items: JSON.parse(JSON.stringify(_store.boardPosts)).reverse(),
          sourceUrl: LOCAL_METADATA.sourceUrl,
          retrievedAt: LOCAL_METADATA.retrievedAt,
          freshnessState: LOCAL_METADATA.freshnessState
        };
      });
    },

    /**
     * Fetch current board posts
     * @returns {Promise<Array>}
     */
    getBoardPosts: function() {
      return this.getBoardSnapshot().then(function(snapshot) {
        return snapshot.items;
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
        return Object.assign({}, newPost, {
          sourceUrl: LOCAL_METADATA.sourceUrl,
          retrievedAt: LOCAL_METADATA.retrievedAt,
          freshnessState: LOCAL_METADATA.freshnessState
        });
      });
    }
  };

  window.CitizenContentAdapter = CitizenContentAdapter;
})();
