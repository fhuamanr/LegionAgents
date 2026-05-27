<div>
  <h1>Shopping Cart</h1>
  <ul>
    {cartItems.map(item => (
      <li key={item.id}>{item.name} - ${item.price}</li>
    ))}
  </ul>
</div>