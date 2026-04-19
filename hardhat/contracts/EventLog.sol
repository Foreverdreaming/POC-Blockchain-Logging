// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";

contract EventLog is AccessControl {
    bytes32 public constant LOGGER_ROLE = keccak256("LOGGER_ROLE");

    event EventLogged(
        bytes32 indexed recordId,
        string action,          // Option B: readable
        bytes32 detailsHash,    // details of event in hash
        string uri,            // where the offline data lives
        address indexed actor, // actor's wallet
        uint256 seq,           // sequence of record, eg. ORDER_1/event 1 (crawl check)-> ORDER_1/event 2 (graph insert)
        uint256 timestamp   // ← block timestamp
    );

    mapping(bytes32 => uint256) public lastSeq;

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(LOGGER_ROLE, admin);
    }

    function commitLog(
        bytes32 recordId,
        string calldata action,
        bytes32 detailsHash,
        string calldata uri
    ) external onlyRole(LOGGER_ROLE) {
        uint256 seq = lastSeq[recordId] + 1;
        lastSeq[recordId] = seq;

        emit EventLogged(recordId, action, detailsHash, uri, msg.sender, seq, block.timestamp);
    }
}
