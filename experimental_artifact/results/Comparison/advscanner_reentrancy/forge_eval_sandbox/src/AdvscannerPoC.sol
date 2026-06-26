// This is a hypothetical vulnerable contract based on the analysis.
import "@openzeppelin/contracts/token/ERC721/ERC721.sol";

contract Guitarist is ERC721 {
    mapping(address => bool) public hasClaimed;
    uint256 public constant MAX_SUPPLY = 10;
    uint256 public currentSupply;

    constructor() ERC721("Guitarist", "GTR") {}

    function purchaseAccess() public payable {
        require(msg.value == 0.1 ether, "Must pay 0.1 ETH");
        // For simplicity, we just check payment, not storing balances.
        // In a real scenario, this might grant a role or flag.
    }

    // Vulnerable function
    function claimGuitar() public {
        require(!hasClaimed[msg.sender], "You have already claimed a guitar.");
        require(currentSupply < MAX_SUPPLY, "All guitars have been claimed.");

        currentSupply++;
        // The external call to the attacker happens here via _safeMint
        _safeMint(msg.sender, currentSupply);

        // State is updated AFTER the external call, allowing reentrancy
        hasClaimed[msg.sender] = true;
    }
}